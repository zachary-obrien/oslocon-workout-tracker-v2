import anvil.server

from formatting_service import normalize_for_match, smart_title_case
from table_helpers import search_exercises_by_query, get_first_exercise_image
from anvil.tables import app_tables


LEGACY_NAME_ALIASES = {
    normalize_for_match("Dumbell Row (2-Arm)"): "Bent Over Two-Dumbbell Row",
    normalize_for_match("Dumbbell Press (Medium Incline)"): "Incline Dumbbell Press",
    normalize_for_match("Dumbell Curl (2 Arm)"): "Dumbbell Bicep Curl",
    normalize_for_match("Dumbbell Skull Crusher"): "Standing Dumbbell Triceps Extension",
    normalize_for_match("Dumbell Split Squat"): "Split Squat with Dumbbells",
    normalize_for_match("Bodyweight Squat"): "Bodyweight Squat",
    normalize_for_match("Dumbbell Lateral Raise"): "Side Lateral Raise",
    normalize_for_match("Dumbell Stiff Legged Deadlift"): "Stiff-Legged Dumbbell Deadlift",
    normalize_for_match("Standing Calf Raise"): "Standing Calf Raises",
}


def get_canonical_exercise_by_name(name):
    normalized = normalize_for_match(name)
    canonical = LEGACY_NAME_ALIASES.get(normalized, smart_title_case(name))
    target_norm = normalize_for_match(canonical)

    rows = list(app_tables.exercises.search(is_active=True))
    exact = [r for r in rows if normalize_for_match(r["normalized_name"] or r["name"]) == target_norm]
    if exact:
        return exact[0]

    contains = [r for r in rows if target_norm in normalize_for_match(r["normalized_name"] or r["name"])]
    if len(contains) == 1:
        return contains[0]
    if len(contains) > 1:
        raise Exception(f"Ambiguous exercise mapping for '{name}'.")
    raise Exception(f"Could not find exercise '{name}' in exercises table.")


def serialize_exercise_option(row):
    image_row = get_first_exercise_image(row)
    return {
        "exercise_id": row.get_id(),
        "name": row["name"],
        "normalized_name": row["normalized_name"],
        "equipment": row["equipment"],
        "category": row["category"],
        "uses_bodyweight_default": row["uses_bodyweight_default"],
        "primary_muscles": row["primary_muscles"] or [],
        "image_media": image_row["image"] if image_row else None,
    }


@anvil.server.callable
def search_exercise_options(query):
    return [serialize_exercise_option(r) for r in search_exercises_by_query(query, 30)]
