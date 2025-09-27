from src.ai.recipes_llm import generate_recipes_ai
from src.nutrition.ingredients import INGREDIENTS


def fake_llm_ok(prompt: str) -> str:
    # returns a JSON array with one recipe using tofu, rice, broccoli
    return '''[
    {
        "title": "Tofu Rice Bowl",
        "ingredients": [
            {"id": "tofu", "name": "Tofu", "qty_g": 200},
            {"id": "rice", "name": "Rice (white)", "qty_g": 150},
            {"id": "broccoli", "name": "Broccoli", "qty_g": 100}
        ],
        "steps": ["Cook rice.", "Sauté tofu.", "Steam broccoli."],
        "nutrition": {"kcal": 600, "protein_g": 35, "carbs_g": 80, "fat_g": 12},
        "warnings": []
    }
]'''


def test_generate_recipes_ai_scaling():
    allowed = INGREDIENTS
    targets = {"calories": 700}
    recipes = generate_recipes_ai(allowed, targets, max_recipes=1, llm_call=fake_llm_ok)
    assert isinstance(recipes, list)
    assert len(recipes) == 1
    r = recipes[0]
    assert "nutrition" in r
    # nutrition kcal should be close to target (allow some tolerance)
    assert abs(r["nutrition"]["kcal"] - 700) < 5
