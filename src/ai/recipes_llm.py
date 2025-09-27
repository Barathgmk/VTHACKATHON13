"""LLM-backed recipe generator with deterministic validation and scaling.

This module provides generate_recipes_ai which accepts allowed ingredients and
target macros and returns validated recipes. It can accept an optional llm_call
callable for testing (llm_call(prompt) -> str).
"""
import json
import os
from typing import List, Dict, Callable, Optional


def build_prompt(allowed_ingredients: List[Dict], targets: Dict, max_recipes: int = 2) -> str:
    # Build a constrained prompt with allowed ingredient ids and names and a strict JSON schema example
    allowed = [{"id": i["id"], "name": i["name"]} for i in allowed_ingredients]
    prompt = {
        "instructions": (
            "You are a recipe assistant. Only use ingredients from the allowed_ingredients list. "
            "Output JSON only. Return an array of up to {max_recipes} recipes. Each recipe must follow this schema: "
            "{title, ingredients:[{id,name,qty_g}], steps:[str], nutrition:{kcal,protein_g,carbs_g,fat_g}, warnings:[]}."
        ),
        "allowed_ingredients": allowed,
        "targets": targets,
        "max_recipes": max_recipes,
        "example": {
            "title": "Tofu Rice Bowl",
            "ingredients": [
                {"id": "tofu", "name": "Tofu", "qty_g": 200},
                {"id": "rice", "name": "Rice (white)", "qty_g": 150},
                {"id": "broccoli", "name": "Broccoli", "qty_g": 100}
            ],
            "steps": ["Cook rice.", "Sauté tofu.", "Steam broccoli and assemble bowl."],
            "nutrition": {"kcal": 600, "protein_g": 35.0, "carbs_g": 80.0, "fat_g": 12.0},
            "warnings": []
        }
    }
    return json.dumps(prompt)


def _call_llm(prompt: str, llm_call: Optional[Callable[[str], str]] = None) -> str:
    if llm_call is not None:
        return llm_call(prompt)

    try:
        import openai
    except Exception as e:
        raise RuntimeError("OpenAI package not available; provide llm_call for testing") from e

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set; provide llm_call for testing")
    openai.api_key = api_key

    # Use chat completion with a single user message containing the JSON prompt
    resp = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], max_tokens=800)
    return resp["choices"][0]["message"]["content"]


def _compute_nutrition_for_recipe(recipe: Dict, allowed_by_id: Dict[str, Dict]) -> Dict[str, float]:
    kcal = 0.0
    protein = 0.0
    carbs = 0.0
    fat = 0.0
    for ing in recipe.get("ingredients", []):
        iid = ing.get("id")
        qty = float(ing.get("qty_g", 0.0))
        if iid not in allowed_by_id:
            raise ValueError(f"ingredient {iid} not allowed")
        nut = allowed_by_id[iid]["nutrition_per_100g"]
        kcal += nut["kcal"] * qty / 100.0
        protein += nut["protein_g"] * qty / 100.0
        carbs += nut["carbs_g"] * qty / 100.0
        fat += nut["fat_g"] * qty / 100.0
    return {"kcal": round(kcal, 1), "protein_g": round(protein, 1), "carbs_g": round(carbs, 1), "fat_g": round(fat, 1)}


def _scale_recipe_quantities(recipe: Dict, scale: float) -> Dict:
    for ing in recipe.get("ingredients", []):
        qty = float(ing.get("qty_g", 0.0))
        ing["qty_g"] = round(qty * scale, 1)
    return recipe


def validate_and_scale(recipe: Dict, allowed_ingredients: List[Dict], targets: Dict, tolerance: float = 0.10) -> Dict:
    allowed_by_id = {i["id"]: i for i in allowed_ingredients}
    # ensure recipe only uses allowed ids
    for ing in recipe.get("ingredients", []):
        if ing.get("id") not in allowed_by_id:
            raise ValueError(f"recipe uses disallowed ingredient: {ing.get('id')}")

    actual = _compute_nutrition_for_recipe(recipe, allowed_by_id)
    target_kcal = float(targets.get("calories", targets.get("kcal", 0)))
    if target_kcal <= 0:
        return recipe

    # If within tolerance, return with computed nutrition
    diff = abs(actual["kcal"] - target_kcal) / max(1.0, target_kcal)
    if diff <= tolerance:
        recipe["nutrition"] = actual
        return recipe

    # else, scale quantities proportionally by calorie ratio
    scale = target_kcal / max(1e-6, actual["kcal"])
    scaled = _scale_recipe_quantities(recipe, scale)
    scaled_actual = _compute_nutrition_for_recipe(scaled, allowed_by_id)
    scaled["nutrition"] = scaled_actual
    return scaled


def generate_recipes_ai(allowed_ingredients: List[Dict], targets: Dict, max_recipes: int = 2, llm_call: Optional[Callable[[str], str]] = None) -> List[Dict]:
    """Generate recipes using an LLM then validate/scale them deterministically.

    llm_call: optional function receiving the prompt string and returning the LLM text output.
    """
    if not allowed_ingredients:
        raise ValueError("no allowed ingredients")

    prompt = build_prompt(allowed_ingredients, targets, max_recipes)
    text = _call_llm(prompt, llm_call=llm_call)

    # attempt to parse JSON from the LLM response
    try:
        parsed = json.loads(text)
    except Exception:
        # Some LLMs may wrap JSON in markdown; try to extract the first JSON object/array
        import re

        m = re.search(r"(\[\s*\{.*\}\s*\])", text, flags=re.S)
        if not m:
            raise ValueError("LLM did not return valid JSON")
        parsed = json.loads(m.group(1))

    if not isinstance(parsed, list):
        # allow single recipe as object
        if isinstance(parsed, dict):
            parsed = [parsed]
        else:
            raise ValueError("parsed LLM output is not a recipe list or object")

    validated = []
    for r in parsed[:max_recipes]:
        v = validate_and_scale(r, allowed_ingredients, targets)
        validated.append(v)
    return validated
