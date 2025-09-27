"""Simple FastAPI server exposing calorie/macro calculations and plan generation for MVP."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src.nutrition.targets import calculate_bmr, calculate_tdee, calculate_calorie_target, calculate_macros
from src.nutrition.ingredients import INGREDIENTS, filter_by_diet, find_affordable
from src.recipes import generate_simple_recipes
from src.ai.recipes_llm import generate_recipes_ai

app = FastAPI(title="EZDiet MVP API")

# serve the simple frontend
app.mount("/", StaticFiles(directory="web", html=True), name="web")

# enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GoalFirstIn(BaseModel):
    sex: str = Field(..., description="male or female")
    age: int
    height_cm: float
    weight_kg: float
    activity: str
    goal: str = Field(..., description="lose|maintain|gain")
    weekly_rate_kg: Optional[float] = 0.5
    dietary_restrictions: Optional[List[str]] = []
    budget: Optional[float] = 20.0


class NumbersFirstIn(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    dietary_restrictions: Optional[List[str]] = []
    budget: Optional[float] = 20.0


class PlanOut(BaseModel):
    calories: float
    macros: dict
    shopping_list: List[dict]
    recipes: List[dict]


@app.post("/calculate_goal", response_model=PlanOut)
def calculate_goal(data: GoalFirstIn):
    try:
        bmr = calculate_bmr(data.sex, data.weight_kg, data.height_cm, data.age)
        tdee = calculate_tdee(bmr, data.activity)
        calories = calculate_calorie_target(tdee, data.goal, data.weekly_rate_kg)
        macros = calculate_macros(calories, data.weight_kg)

        # filter ingredients by diet and affordability
        allowed = filter_by_diet(INGREDIENTS, data.dietary_restrictions or [])
        shopping = find_affordable(allowed, data.budget or 0.0)
        recipes = generate_simple_recipes(shopping, macros, max_recipes=2)

        return PlanOut(calories=calories, macros=macros, shopping_list=shopping, recipes=recipes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/calculate_numbers", response_model=PlanOut)
def calculate_numbers(data: NumbersFirstIn):
    # validate totals roughly
    total_kcal = data.calories
    macros = {"calories": total_kcal, "protein_g": data.protein_g, "carbs_g": data.carbs_g, "fat_g": data.fat_g}

    allowed = filter_by_diet(INGREDIENTS, data.dietary_restrictions or [])
    shopping = find_affordable(allowed, data.budget or 0.0)
    recipes = generate_simple_recipes(shopping, macros, max_recipes=2)

    return PlanOut(calories=total_kcal, macros=macros, shopping_list=shopping, recipes=recipes)


@app.post("/generate_recipes_ai", response_model=List[dict])
def generate_recipes_ai_endpoint(calories: float = 600, dietary_restrictions: Optional[List[str]] = [], budget: float = 20.0):
    # select allowed & affordable ingredients first
    allowed = filter_by_diet(INGREDIENTS, dietary_restrictions or [])
    shopping = find_affordable(allowed, budget or 0.0)

    targets = {"calories": calories}
    try:
        recipes = generate_recipes_ai(shopping, targets, max_recipes=2)
    except RuntimeError as e:
        # likely missing OPENAI_API_KEY or openai package; return 503-style error
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return recipes
