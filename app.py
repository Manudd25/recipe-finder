from flask import Flask, render_template, request, redirect, url_for
import requests
import os
import random
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Use your V2 base from .env (e.g. https://www.themealdb.com/api/json/v2/65232507/)
BASE_URL = os.getenv("BASE_URL", "https://www.themealdb.com/api/json/v1/1/")
if not BASE_URL.endswith("/"):
    BASE_URL += "/"

# --- Helpers ---------------------------------------------------------------

def api_get(path, params=None):
    """GET wrapper that builds a full API URL and returns parsed JSON (or {})."""
    try:
        resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=12)
        resp.raise_for_status()
        return resp.json() or {}
    except Exception:
        return {}

def normalize_ingredient(txt: str) -> str:
    return txt.strip().lower().replace(" ", "_")

SYNONYMS = {
    "pasta": ["spaghetti", "penne", "rigatoni", "macaroni", "fettuccine", "linguine", "tagliatelle", "fusilli", "pasta"],
    "tomato": ["tomato", "tomatoes", "cherry_tomatoes"],
    "egg": ["egg", "eggs", "egg_yolk", "egg_yolks", "egg_white", "egg_whites"],
    "chili": ["chili", "chilli", "red_chili", "red_chilli"],
    "salad": ["lettuce", "salad_leaves", "mixed_salad", "romaine_lettuce"],
    "cheese": ["cheese", "parmesan_cheese", "cheddar_cheese", "mozzarella"],
    "beef": ["beef", "minced_beef", "ground_beef"],
    "chicken_breast": ["chicken_breast", "chicken"],
    "spring_onion": ["spring_onion", "green_onion", "scallions"],
}

def fetch_random_recipes(n=6):
    seen = set()
    out = []
    while len(out) < n:
        data = api_get("random.php")
        meals = data.get("meals") or []
        if not meals:
            break
        meal = meals[0]
        mid = meal.get("idMeal")
        if mid and mid not in seen:
            seen.add(mid)
            out.append({
                "idMeal": mid,
                "name": meal.get("strMeal"),
                "image": meal.get("strMealThumb"),
                "description": None,
            })
    return out

def fetch_recipe_by_id(meal_id):
    data = api_get("lookup.php", params={"i": meal_id})
    meals = data.get('meals')
    if not meals:
        return {}
    return meals[0]

def map_meals_to_cards(meals):
    cards = []
    for m in meals:
        cards.append({
            "idMeal": m.get("idMeal"),
            "name": m.get("strMeal"),
            "image": m.get("strMealThumb"),
            "description": None,
        })
    return cards

def search_recipes(user_input: str):
    """
    1) Try exact multi-ingredient match
    2) If none, fallback to fuzzy union (synonyms, single ingredients)
    """
    raw_parts = [p.strip() for p in (user_input or "").split(",") if p.strip()]
    if not raw_parts:
        return []

    normalized = [normalize_ingredient(p) for p in raw_parts]

    # --- (1) Exact multi-ingredient match (all ingredients together)
    exact = api_get("filter.php", params={"i": ",".join(normalized)}).get("meals") or []
    if exact:
        return map_meals_to_cards(exact)

    # --- (2) Fallback: fuzzy / single ingredient matches
    expanded_terms = {base: SYNONYMS.get(base, [base]) for base in normalized}

    score = {}       # meal_id -> number of matched base ingredients
    meal_cache = {}  # meal_id -> meal info

    for base, terms in expanded_terms.items():
        for t in terms:
            meals = api_get("filter.php", params={"i": t}).get("meals") or []
            for m in meals:
                mid = m.get("idMeal")
                if not mid:
                    continue
                meal_cache[mid] = m
                score.setdefault(mid, set()).add(base)

    if not score:
        return []

    # --- prioritize meals that match the most user ingredients
    ranked_ids = sorted(score.keys(), key=lambda k: (-len(score[k]), meal_cache[k].get("strMeal", "")))
    ranked_meals = [meal_cache[mid] for mid in ranked_ids]

    return map_meals_to_cards(ranked_meals)

# --- Routes ----------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    recipes = []
    no_results = False
    random_recipes = []

    if request.method == "POST":
        ingredients = request.form.get("ingredients", "")
        recipes = search_recipes(ingredients)
        if not recipes:
            no_results = True
    else:
        random_recipes = fetch_random_recipes(6)

    return render_template(
        "index.html",
        recipes=recipes,
        no_results=no_results,
        random_recipes=random_recipes
    )

@app.route("/hot-meals")
def trend():
    random_recipes = fetch_random_recipes(6)
    return render_template(
        "index.html",
        recipes=[],
        no_results=False,
        random_recipes=random_recipes
    )

@app.route("/ideas")
def ideas():
    pairs = ["chicken, garlic", "shrimp, chili", "beef, tomato", "mushroom, cream", "zucchini, feta"]
    recipes = search_recipes(random.choice(pairs))
    if not recipes:
        return redirect(url_for("trend"))
    return render_template(
        "index.html",
        recipes=recipes,
        no_results=False,
        random_recipes=[]
    )

@app.route("/inspire-me")
def inspire():
    random_recipes = fetch_random_recipes(6)
    return render_template(
        "index.html",
        recipes=[],
        no_results=False,
        random_recipes=random_recipes
    )

@app.route("/recipe/<meal_id>")
def recipe(meal_id):
    meal = fetch_recipe_by_id(meal_id)
    if not meal:
        return redirect(url_for("index"))
    return render_template("recipe.html", meal=meal)

if __name__ == "__main__":
    app.run(debug=True)
