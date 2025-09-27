"""Calorie and macro target calculator.

Implements Mifflin-St Jeor BMR, TDEE, calorie adjustment for goals,
and macro allocation (protein per kg, fat pct, carbs remainder).
"""
from typing import Literal, Dict


ActivityMultiplier = Literal["sedentary", "light", "moderate", "active", "very_active"]

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}


def calculate_bmr(sex: Literal["male", "female"], weight_kg: float, height_cm: float, age: int) -> float:
    """Calculate BMR using Mifflin-St Jeor equation.

    Args:
        sex: 'male' or 'female'
        weight_kg: weight in kilograms
        height_cm: height in centimeters
        age: age in years

    Returns:
        BMR in kcal/day
    """
    if sex not in ("male", "female"):
        raise ValueError("sex must be 'male' or 'female'")
    if weight_kg <= 0 or height_cm <= 0 or age <= 0:
        raise ValueError("weight, height, and age must be positive")

    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age
    bmr += 5 if sex == "male" else -161
    return float(bmr)


def calculate_tdee(bmr: float, activity: ActivityMultiplier) -> float:
    """Calculate TDEE by applying activity multiplier to BMR."""
    if activity not in ACTIVITY_FACTORS:
        raise ValueError(f"unknown activity level: {activity}")
    return float(bmr * ACTIVITY_FACTORS[activity])


def calculate_calorie_target(tdee: float, goal: Literal["lose", "maintain", "gain"], weekly_rate_kg: float = 0.5) -> float:
    """Adjust calories based on goal.

    Args:
        tdee: maintenance calories
        goal: 'lose'|'maintain'|'gain'
        weekly_rate_kg: desired kg per week (positive); for loss/gain, typical 0.25-1.0 kg

    Returns:
        daily calorie target
    """
    if weekly_rate_kg < 0:
        raise ValueError("weekly_rate_kg must be non-negative")

    # Approx 7700 kcal per kg of body weight
    kcal_per_kg = 7700
    daily_delta = (weekly_rate_kg * kcal_per_kg) / 7.0

    if goal == "maintain":
        return float(tdee)
    if goal == "lose":
        # for safety, cap daily deficit so calories don't go below 1200/1500
        target = tdee - daily_delta
        return float(max(target, 1200.0))
    if goal == "gain":
        target = tdee + daily_delta
        return float(target)

    raise ValueError("goal must be 'lose', 'maintain', or 'gain'")


def calculate_macros(calories: float, weight_kg: float, protein_g_per_kg: float = 1.8, fat_pct: float = 0.25) -> Dict[str, float]:
    """Allocate macros (protein/g, carbs/g, fat/g) given targets.

    Args:
        calories: daily calorie target
        weight_kg: user's weight in kg (for protein calculation)
        protein_g_per_kg: grams of protein per kg bodyweight
        fat_pct: fraction of calories from fat (0.20-0.35 recommended)

    Returns:
        dict with keys: calories, protein_g, fat_g, carbs_g
    """
    if calories <= 0 or weight_kg <= 0:
        raise ValueError("calories and weight_kg must be positive")
    if protein_g_per_kg <= 0:
        raise ValueError("protein_g_per_kg must be positive")
    if not (0.1 <= fat_pct <= 0.5):
        raise ValueError("fat_pct must be between 0.1 and 0.5")

    protein_g = protein_g_per_kg * weight_kg
    protein_kcal = protein_g * 4

    fat_kcal = calories * fat_pct
    fat_g = fat_kcal / 9

    remaining_kcal = calories - (protein_kcal + fat_kcal)
    carbs_g = max(0.0, remaining_kcal / 4)

    return {
        "calories": float(calories),
        "protein_g": round(protein_g, 1),
        "fat_g": round(fat_g, 1),
        "carbs_g": round(carbs_g, 1),
    }
