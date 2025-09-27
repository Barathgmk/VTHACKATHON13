from src.recipes import generate_simple_recipes
from src.nutrition.ingredients import INGREDIENTS


def test_generate_simple_recipes_has_nutrition_and_cost():
    allowed = INGREDIENTS
    targets = {"calories": 600}
    recs = generate_simple_recipes(allowed, targets, max_recipes=1)
    assert isinstance(recs, list)
    assert len(recs) == 1
    r = recs[0]
    assert "nutrition" in r
    assert "kcal" in r["nutrition"]
    assert abs(r["nutrition"]["kcal"] - 600) < 80  # generous tolerance for naive generator
    assert "cost_estimate_usd" in r
    assert r["cost_estimate_usd"] >= 0


def test_generate_simple_recipes_protein_target_increases_protein():
    allowed = INGREDIENTS
    base_targets = {"calories": 600}
    high_protein_targets = {"calories": 600, "protein_g": 100}

    base = generate_simple_recipes(allowed, base_targets, max_recipes=1)[0]
    high = generate_simple_recipes(allowed, high_protein_targets, max_recipes=1)[0]

    assert high["nutrition"]["protein_g"] >= base["nutrition"]["protein_g"]


def test_optimizer_reduces_protein_error():
    from src.recipes import generate_simple_recipes, _compute_nutrition_and_cost, _scale_recipe_to_targets
    from src.nutrition.ingredients import INGREDIENTS

    allowed = INGREDIENTS
    targets = {"calories": 600, "protein_g": 80}
    # create initial recipe without optimizer step
    recipe = generate_simple_recipes(allowed, {"calories": 600}, max_recipes=1)[0]
    allowed_by_id = {i['id']: i for i in allowed}
    before = _compute_nutrition_and_cost(recipe, allowed_by_id)
    # run scaler which will call optimizer
    scaled = _scale_recipe_to_targets(recipe, allowed_by_id, targets)
    after = _compute_nutrition_and_cost(scaled, allowed_by_id)

    before_err = abs((before['protein_g'] - targets['protein_g']))
    after_err = abs((after['protein_g'] - targets['protein_g']))
    assert after_err <= before_err


def test_pulp_cost_minimization_if_available():
    try:
        import pulp  # type: ignore
    except Exception:
        import pytest

        pytest.skip("pulp not installed; skipping cost-minimization test")

    from src.recipes import generate_simple_recipes
    allowed = INGREDIENTS
    targets = {"calories": 600, "protein_g": 30, "minimize_cost": True}
    recs = generate_simple_recipes(allowed, targets, max_recipes=1)
    r = recs[0]
    assert "cost_estimate_usd" in r
    assert r["cost_estimate_usd"] >= 0
