"""Cost-minimization optimizer using PuLP.

This module requires the `pulp` package. It minimizes total ingredient cost
subject to macro and calorie bounds (within a tolerance).
"""
from typing import Dict


def optimize_cost(recipe: Dict, allowed_by_id: Dict[str, Dict], targets: Dict, tol: float = 0.05, max_qty_g: float = 2000.0):
    try:
        import pulp
    except Exception as e:
        raise ImportError("PuLP is required for cost optimization. Install with 'pip install pulp'.") from e

    ings = recipe.get("ingredients", [])
    if not ings:
        return recipe

    n = len(ings)

    # build densities per gram
    prot = []
    carbs = []
    fat = []
    kcal = []
    price = []
    for ing in ings:
        iid = ing.get("id")
        meta = allowed_by_id.get(iid, {})
        nut = meta.get("nutrition_per_100g", {})
        prot.append(nut.get("protein_g", 0.0) / 100.0)
        carbs.append(nut.get("carbs_g", 0.0) / 100.0)
        fat.append(nut.get("fat_g", 0.0) / 100.0)
        kcal.append(nut.get("kcal", 0.0) / 100.0)
        price.append(meta.get("price_per_100g", 0.0) / 100.0)

    # create LP
    prob = pulp.LpProblem("recipe_cost_min", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", lowBound=0, upBound=max_qty_g) for i in range(n)]

    # objective: minimize total price = sum(price_i * x_i)
    prob += pulp.lpSum([price[i] * x[i] for i in range(n)])

    # constraints: for each target, enforce bounds within tolerance if provided
    def add_bound(density_list, key):
        if key in targets:
            tgt = float(targets[key])
            low = tgt * (1.0 - tol)
            high = tgt * (1.0 + tol)
            prob += pulp.lpSum([density_list[i] * x[i] for i in range(n)]) >= low
            prob += pulp.lpSum([density_list[i] * x[i] for i in range(n)]) <= high

    add_bound(prot, "protein_g")
    add_bound(carbs, "carbs_g")
    add_bound(fat, "fat_g")
    # calories target may be 'calories' or 'kcal'
    cal_key = "calories" if "calories" in targets else ("kcal" if "kcal" in targets else None)
    if cal_key:
        tgt = float(targets.get(cal_key, 0.0))
        low = tgt * (1.0 - tol)
        high = tgt * (1.0 + tol)
        prob += pulp.lpSum([kcal[i] * x[i] for i in range(n)]) >= low
        prob += pulp.lpSum([kcal[i] * x[i] for i in range(n)]) <= high

    # solve
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # write back solution
    for i, ing in enumerate(ings):
        val = x[i].varValue
        if val is None:
            val = ing.get("qty_g", 0.0)
        ing["qty_g"] = round(float(val), 1)

    return recipe
