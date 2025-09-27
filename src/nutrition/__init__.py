"""Nutrition utilities package."""

from .targets import (
    calculate_bmr,
    calculate_tdee,
    calculate_calorie_target,
    calculate_macros,
)

__all__ = [
    "calculate_bmr",
    "calculate_tdee",
    "calculate_calorie_target",
    "calculate_macros",
]
