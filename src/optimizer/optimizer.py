"""Simple optimizer (projected gradient descent) to adjust ingredient quantities to meet macro targets.

This is intentionally lightweight and dependency-free. It operates on small vectors (few ingredients).
"""
from typing import Dict, List


def _compute_preds(A: List[List[float]], x: List[float]) -> List[float]:
    # A is m x n, x is n; returns m
    m = len(A)
    n = len(x)
    preds = [0.0] * m
    for i in range(m):
        s = 0.0
        row = A[i]
        for j in range(n):
            s += row[j] * x[j]
        preds[i] = s
    return preds


def _compute_gradient(A: List[List[float]], preds: List[float], targets: List[float]) -> List[float]:
    # grad = 2 * A^T (preds - targets)
    m = len(A)
    n = len(A[0])
    grad = [0.0] * n
    for j in range(n):
        s = 0.0
        for i in range(m):
            s += A[i][j] * (preds[i] - targets[i])
        grad[j] = 2.0 * s
    return grad


def optimize_quantities(recipe: Dict, allowed_by_id: Dict[str, Dict], targets: Dict, max_qty_g: float = 2000.0, iters: int = 2000, lr: float = 0.01) -> Dict:
    """Optimize ingredient quantities in `recipe` to match numeric targets.

    targets: dict may contain keys 'protein_g','carbs_g','fat_g','calories'
    Returns the recipe modified in-place.
    """
    # Build list of ingredients in recipe
    ings = recipe.get("ingredients", [])
    n = len(ings)
    if n == 0:
        return recipe

    # build A matrix rows: protein, carbs, fat, kcal (only include rows requested)
    rows = []
    row_keys = []
    if "protein_g" in targets:
        rows.append([])
        row_keys.append("protein_g")
    if "carbs_g" in targets:
        rows.append([])
        row_keys.append("carbs_g")
    if "fat_g" in targets:
        rows.append([])
        row_keys.append("fat_g")
    if "calories" in targets or "kcal" in targets:
        rows.append([])
        row_keys.append("kcal")

    # fill columns: each row i has n entries
    for ing in ings:
        iid = ing.get("id")
        meta = allowed_by_id.get(iid, {})
        nut = meta.get("nutrition_per_100g", {})
        prot = nut.get("protein_g", 0.0) / 100.0
        carbs = nut.get("carbs_g", 0.0) / 100.0
        fat = nut.get("fat_g", 0.0) / 100.0
        kcal = nut.get("kcal", 0.0) / 100.0
        for rkey_index, rkey in enumerate(row_keys):
            if rkey == "protein_g":
                rows[rkey_index].append(prot)
            elif rkey == "carbs_g":
                rows[rkey_index].append(carbs)
            elif rkey == "fat_g":
                rows[rkey_index].append(fat)
            elif rkey == "kcal":
                rows[rkey_index].append(kcal)

    # targets vector
    tvec = []
    for rk in row_keys:
        if rk == "kcal":
            tvec.append(float(targets.get("calories", targets.get("kcal", 0.0))))
        else:
            tvec.append(float(targets.get(rk, 0.0)))

    # initial x from recipe qtys
    x = [float(ing.get("qty_g", 100.0)) for ing in ings]

    # perform projected gradient descent
    if len(rows) == 0:
        return recipe

    A = rows  # m x n

    for _ in range(iters):
        preds = _compute_preds(A, x)
        grad = _compute_gradient(A, preds, tvec)
        # update
        for j in range(n):
            x[j] -= lr * grad[j]
            # projection
            if x[j] < 0.0:
                x[j] = 0.0
            if x[j] > max_qty_g:
                x[j] = max_qty_g

    # write back quantities
    for j, ing in enumerate(ings):
        ing["qty_g"] = round(x[j], 1)

    return recipe
