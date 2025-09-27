"""Simple in-memory ingredient catalog and lookup helpers for MVP.

This mock is used to simulate nearby-available ingredients and costs.
Each ingredient contains: name, tags (dietary), price_per_unit ($ per 100g),
and nutrition per 100g (kcal, protein_g, carbs_g, fat_g).
"""
from typing import List, Dict, Iterable


INGREDIENTS: List[Dict] = [
    {"id": "chicken_breast", "name": "Chicken Breast", "tags": ["meat", "gluten_free"], "price_per_100g": 1.2, "nutrition_per_100g": {"kcal": 165, "protein_g": 31.0, "carbs_g": 0.0, "fat_g": 3.6}},
    {"id": "tofu", "name": "Tofu", "tags": ["vegan", "vegetarian", "gluten_free"], "price_per_100g": 0.8, "nutrition_per_100g": {"kcal": 76, "protein_g": 8.0, "carbs_g": 1.9, "fat_g": 4.8}},
    {"id": "salmon", "name": "Salmon", "tags": ["fish", "gluten_free"], "price_per_100g": 2.5, "nutrition_per_100g": {"kcal": 208, "protein_g": 20.4, "carbs_g": 0.0, "fat_g": 13.4}},
    {"id": "rice", "name": "Rice (white)", "tags": ["vegan", "vegetarian", "gluten_free"], "price_per_100g": 0.4, "nutrition_per_100g": {"kcal": 130, "protein_g": 2.4, "carbs_g": 28.0, "fat_g": 0.3}},
    {"id": "pasta", "name": "Pasta", "tags": ["vegan", "vegetarian"], "price_per_100g": 0.6, "nutrition_per_100g": {"kcal": 131, "protein_g": 5.0, "carbs_g": 25.0, "fat_g": 1.1}},
    {"id": "broccoli", "name": "Broccoli", "tags": ["vegan", "vegetarian", "gluten_free"], "price_per_100g": 0.9, "nutrition_per_100g": {"kcal": 34, "protein_g": 2.8, "carbs_g": 6.6, "fat_g": 0.4}},
    {"id": "spinach", "name": "Spinach", "tags": ["vegan", "vegetarian", "gluten_free"], "price_per_100g": 1.0, "nutrition_per_100g": {"kcal": 23, "protein_g": 2.9, "carbs_g": 3.6, "fat_g": 0.4}},
    {"id": "eggs", "name": "Eggs", "tags": ["vegetarian", "gluten_free"], "price_per_100g": 0.7, "nutrition_per_100g": {"kcal": 155, "protein_g": 13.0, "carbs_g": 1.1, "fat_g": 11.0}},
    {"id": "lentils", "name": "Lentils", "tags": ["vegan", "vegetarian", "gluten_free"], "price_per_100g": 0.5, "nutrition_per_100g": {"kcal": 116, "protein_g": 9.0, "carbs_g": 20.0, "fat_g": 0.4}},
    {"id": "milk", "name": "Milk (cow)", "tags": ["vegetarian"], "price_per_100g": 0.3, "nutrition_per_100g": {"kcal": 42, "protein_g": 3.4, "carbs_g": 5.0, "fat_g": 1.0}},
]


def filter_by_diet(ingredients: Iterable[Dict], restrictions: List[str]) -> List[Dict]:
    """Return ingredients that satisfy all restrictions (simple tag matching).

    restrictions: list like ['vegan', 'gluten_free'] or allergy items prefixed with 'no_' (e.g., 'no_nuts').
    """
    if not restrictions:
        return list(ingredients)

    res = []
    forbid = {r[3:] for r in restrictions if r.startswith("no_")}
    required = {r for r in restrictions if not r.startswith("no_")}

    for ing in ingredients:
        tags = set(ing.get("tags", []))
        if forbid & tags:
            continue
        if not required.issubset(tags):
            # If required tags are not all present, skip
            continue
        res.append(ing)
    return res


def find_affordable(ingredients: Iterable[Dict], budget: float, max_items: int = 6) -> List[Dict]:
    """Return up to max_items ingredients sorted by price that fit within budget loosely.

    This function doesn't do a perfect knapsack; it prefers cheaper items and returns a short list.
    """
    items = sorted(ingredients, key=lambda i: i.get("price_per_100g", 999.0))
    chosen = []
    est_cost = 0.0
    for item in items:
        # estimate buying 500g of each as a shopping list baseline
        cost = item.get("price_per_100g", 0.0) * 5
        if est_cost + cost > budget and chosen:
            break
        chosen.append(item)
        est_cost += cost
        if len(chosen) >= max_items:
            break
    return chosen
