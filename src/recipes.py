"""Simple recipe template generator for MVP.

Creates very small recipes (bowls, stir-fries) using allowed ingredients and
attempts to match calorie/macros targets by scaling portions.
"""
from typing import List, Dict
from src.nutrition.ingredients import INGREDIENTS


def _compute_nutrition_and_cost(recipe: Dict, allowed_by_id: Dict[str, Dict]) -> Dict:
    """Compute nutrition totals and cost estimate for a recipe.

    Returns a dict: {kcal, protein_g, carbs_g, fat_g, cost_usd}
    """
    kcal = 0.0
    protein = 0.0
    carbs = 0.0
    fat = 0.0
    cost = 0.0
    for ing in recipe.get("ingredients", []):
        iid = ing.get("id")
        qty = float(ing.get("qty_g", 0.0))
        if iid not in allowed_by_id:
            # If ingredient isn't known, skip it in totals
            continue
        meta = allowed_by_id[iid]
        nut = meta.get("nutrition_per_100g", {})
        kcal += nut.get("kcal", 0.0) * qty / 100.0
        protein += nut.get("protein_g", 0.0) * qty / 100.0
        carbs += nut.get("carbs_g", 0.0) * qty / 100.0
        fat += nut.get("fat_g", 0.0) * qty / 100.0
        price_per_100 = meta.get("price_per_100g", 0.0)
        cost += price_per_100 * qty / 100.0

    return {
        "kcal": round(kcal, 1),
        "protein_g": round(protein, 1),
        "carbs_g": round(carbs, 1),
        "fat_g": round(fat, 1),
        "cost_usd": round(cost, 2),
    }


def _scale_recipe_to_targets(recipe: Dict, allowed_by_id: Dict[str, Dict], targets: Dict, tol: float = 0.10) -> Dict:
    """Scale recipe quantities to better match targets (calories & macros).

    Strategy (simple heuristic):
    1. Scale all ingredients proportionally to match target calories if provided.
    2. For each macro (protein, carbs, fat), if still off beyond tolerance, add grams of the
       ingredient in the recipe with highest density for that macro.
    3. Recompute nutrition/cost and attach warnings if adjustments were large.
    """
    warnings = []
    # compute current nutrition
    current = _compute_nutrition_and_cost(recipe, allowed_by_id)

    # Step 1: scale by calories
    target_kcal = float(targets.get("calories", 0) or 0)
    if target_kcal > 0 and current["kcal"] > 0:
        scale_all = target_kcal / current["kcal"]
        # limit extreme scaling
        if scale_all <= 0 or scale_all > 3:
            warnings.append(f"calorie scale factor {scale_all:.2f} out of bounds, clamped")
            scale_all = max(0.1, min(scale_all, 3.0))
        for ing in recipe.get("ingredients", []):
            ing["qty_g"] = round(float(ing.get("qty_g", 0.0)) * scale_all, 1)
        current = _compute_nutrition_and_cost(recipe, allowed_by_id)

    # Helper to adjust a macro by adding grams of the highest-density ingredient
    def _adjust_macro(macro_key: str, target_value: float):
        actual = current.get(macro_key, 0.0)
        need = target_value - actual
        if abs(need) <= max(1.0, abs(target_value) * tol):
            return  # within tolerance

        # find ingredient with highest density for this macro in the recipe
        best = None
        best_density = 0.0
        for ing in recipe.get("ingredients", []):
            iid = ing.get("id")
            meta = allowed_by_id.get(iid)
            if not meta:
                continue
            density = meta.get("nutrition_per_100g", {}).get(macro_key.replace("protein_g", "protein_g").replace("carbs_g", "carbs_g").replace("fat_g", "fat_g"), 0.0)
            if density > best_density:
                best_density = density
                best = ing

        if not best or best_density <= 0:
            warnings.append(f"no suitable ingredient found to adjust {macro_key}")
            return

        # grams needed of that ingredient to supply `need` grams of macro
        grams_needed = (need * 100.0) / best_density
        # clamp addition to avoid absurd portions
        if grams_needed > 1000:
            warnings.append(f"requested addition for {macro_key} too large ({grams_needed:.0f}g), clamped")
            grams_needed = 1000.0
        best["qty_g"] = round(float(best.get("qty_g", 0.0)) + grams_needed, 1)

    # Step 2: adjust macros individually if targets provided
    if "protein_g" in targets:
        _adjust_macro("protein_g", float(targets["protein_g"]))
        current = _compute_nutrition_and_cost(recipe, allowed_by_id)
    if "carbs_g" in targets:
        _adjust_macro("carbs_g", float(targets["carbs_g"]))
        current = _compute_nutrition_and_cost(recipe, allowed_by_id)
    if "fat_g" in targets:
        _adjust_macro("fat_g", float(targets["fat_g"]))
        current = _compute_nutrition_and_cost(recipe, allowed_by_id)

    # attach warnings and updated nutrition/cost
    recipe.setdefault("warnings", []).extend(warnings)

    # Final refinement using optimizer if available
    try:
        # prefer PuLP cost-minimizer if available
        try:
            from src.optimizer.pulp_optimizer import optimize_cost
            # if targets contain a 'minimize_cost' flag True, use cost optimizer
            if targets.get("minimize_cost", False):
                optimize_cost(recipe, allowed_by_id, targets)
            else:
                from src.optimizer.optimizer import optimize_quantities
                optimize_quantities(recipe, allowed_by_id, targets)
        except Exception:
            # fallback to simple optimizer
            from src.optimizer.optimizer import optimize_quantities
            optimize_quantities(recipe, allowed_by_id, targets)
    except Exception:
        # if optimizer missing or fails, continue with heuristic
        pass

    meta = _compute_nutrition_and_cost(recipe, allowed_by_id)
    recipe["nutrition"] = {"kcal": meta["kcal"], "protein_g": meta["protein_g"], "carbs_g": meta["carbs_g"], "fat_g": meta["fat_g"]}
    recipe["cost_estimate_usd"] = meta["cost_usd"]
    return recipe


def generate_simple_recipes(allowed_ingredients: List[Dict], targets: Dict, max_recipes: int = 2) -> List[Dict]:
    """Return simple recipes using only allowed_ingredients.

    targets: {'calories': float, 'protein_g': float, 'carbs_g': float, 'fat_g': float}
    This is intentionally naive: it creates a protein + carb + veg bowl and scales amounts.
    """
    recipes = []
    # classify ingredients
    proteins = [i for i in allowed_ingredients if any(t in i.get('tags', []) for t in ('meat','fish','eggs','tofu','lentils'))]
    carbs = [i for i in allowed_ingredients if any(t in i.get('tags', []) for t in ('vegan','vegetarian')) and i['id'] in ('rice','pasta','lentils')]
    vegs = [i for i in allowed_ingredients if 'vegetarian' in i.get('tags', []) and i['id'] in ('broccoli','spinach')]

    # fallback: if lists are empty, pick any allowed
    if not proteins:
        proteins = allowed_ingredients
    if not carbs:
        carbs = allowed_ingredients
    if not vegs:
        vegs = allowed_ingredients

    allowed_by_id = {i['id']: i for i in allowed_ingredients}

    for p in proteins[:max_recipes]:
        c = carbs[0]
        v = vegs[0]
        # naive: allocate 40% calories to protein source, 40% to carbs, 20% to veg/fat
        cal = targets.get('calories', 600)
        p_cal = cal * 0.4
        c_cal = cal * 0.4
        v_cal = cal * 0.2

        def grams_for_cal(ing, kcal_target):
            kcal_per_100 = ing['nutrition_per_100g']['kcal']
            if kcal_per_100 <= 0:
                return 0.0
            return round((kcal_target / kcal_per_100) * 100, 1)

        p_qty = grams_for_cal(p, p_cal)
        c_qty = grams_for_cal(c, c_cal)
        v_qty = grams_for_cal(v, v_cal)

        recipe = {
            'title': f"{p['name']} & {c['name']} bowl",
            'ingredients': [
                {'id': p['id'], 'name': p['name'], 'qty_g': p_qty},
                {'id': c['id'], 'name': c['name'], 'qty_g': c_qty},
                {'id': v['id'], 'name': v['name'], 'qty_g': v_qty},
            ],
            'steps': [
                'Cook the carb (rice/pasta/lentils) until tender.',
                f'Season and cook the {p["name"].lower()} as appropriate (grill/sauté/bake).',
                f'Steam or sauténe the {v["name"].lower()} and combine into a bowl with the carb and protein.'
            ],
        }
        # compute nutrition and cost, then attempt macro-aware scaling to targets
        recipe = _scale_recipe_to_targets(recipe, allowed_by_id, targets)
        recipes.append(recipe)
        if len(recipes) >= max_recipes:
            break

    return recipes
