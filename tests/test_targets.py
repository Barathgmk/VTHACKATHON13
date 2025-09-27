import pytest

from src.nutrition.targets import (
    calculate_bmr,
    calculate_tdee,
    calculate_calorie_target,
    calculate_macros,
)


def test_bmr_male_example():
    # Example: 80kg, 180cm, 30yo male
    bmr = calculate_bmr("male", 80, 180, 30)
    assert isinstance(bmr, float)
    assert 1700 < bmr < 2100


def test_bmr_female_example():
    bmr = calculate_bmr("female", 60, 165, 28)
    assert isinstance(bmr, float)
    assert 1200 < bmr < 1600


def test_tdee_and_calorie_target_loss():
    bmr = calculate_bmr("male", 90, 185, 35)
    tdee = calculate_tdee(bmr, "moderate")
    # Lose 0.5kg/week
    target = calculate_calorie_target(tdee, "lose", weekly_rate_kg=0.5)
    assert target < tdee
    assert target >= 1200


def test_macros_allocation():
    calories = 2500
    weight = 80
    macros = calculate_macros(calories, weight, protein_g_per_kg=1.8, fat_pct=0.25)
    assert macros["calories"] == float(calories)
    assert macros["protein_g"] == round(1.8 * weight, 1)
    # fat grams roughly calories*0.25/9
    assert abs(macros["fat_g"] - ((calories * 0.25) / 9)) < 0.5


def test_invalid_inputs():
    with pytest.raises(ValueError):
        calculate_bmr("other", 70, 170, 30)
    with pytest.raises(ValueError):
        calculate_tdee(1500, "unknown")
    with pytest.raises(ValueError):
        calculate_calorie_target(2000, "lose", weekly_rate_kg=-1)
    with pytest.raises(ValueError):
        calculate_macros(0, 70)
