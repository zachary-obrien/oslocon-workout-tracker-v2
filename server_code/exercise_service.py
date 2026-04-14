import anvil.server

from formatting_service import normalize_for_match, smart_title_case
from table_helpers import search_exercises_by_query, get_first_exercise_image, get_exercise_images, safe_get
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
  exact = [r for r in rows if normalize_for_match(safe_get(r, "normalized_name", None) or safe_get(r, "name", "")) == target_norm]
  if exact:
    return exact[0]

  contains = [r for r in rows if target_norm in normalize_for_match(safe_get(r, "normalized_name", None) or safe_get(r, "name", ""))]
  if len(contains) == 1:
    return contains[0]
  if len(contains) > 1:
    raise Exception(f"Ambiguous exercise mapping for '{name}'.")
  raise Exception(f"Could not find exercise '{name}' in exercises table.")


def serialize_exercise_option(row):
  image_row = get_first_exercise_image(row)
  primary = safe_get(row, "primary_muscles", []) or []
  secondary = safe_get(row, "secondary_muscles", []) or []
  return {
    "exercise_id": row.get_id(),
    "id": row.get_id(),
    "name": safe_get(row, "name", ""),
    "normalized_name": safe_get(row, "normalized_name", ""),
    "equipment": safe_get(row, "equipment", ""),
    "category": safe_get(row, "category", ""),
    "uses_bodyweight_default": bool(safe_get(row, "uses_bodyweight_default", False)),
    "primary_muscles": primary,
    "secondary_muscles": secondary,
    "muscle_group": primary[0] if primary else "General",
    "group_size": safe_get(row, "group_size", ""),
    "image_media": safe_get(image_row, "image", None) if image_row else None,
  }


def serialize_exercise_detail(row):
  primary = safe_get(row, "primary_muscles", []) or []
  secondary = safe_get(row, "secondary_muscles", []) or []
  instructions = safe_get(row, "instructions", []) or []
  if isinstance(instructions, str):
    instructions = [instructions]
  images = []
  for image_row in get_exercise_images(row):
    images.append({
      "media": safe_get(image_row, "image", None),
      "label": safe_get(image_row, "label", "") or "",
      "sort_order": safe_get(image_row, "sort_order", None),
      "source_filename": safe_get(image_row, "source_filename", "") or "",
    })
  return {
    "exercise_id": row.get_id(),
    "name": safe_get(row, "name", ""),
    "category": safe_get(row, "category", ""),
    "force": safe_get(row, "force", ""),
    "level": safe_get(row, "level", ""),
    "mechanic": safe_get(row, "mechanic", ""),
    "equipment": safe_get(row, "equipment", ""),
    "group_size": safe_get(row, "group_size", ""),
    "uses_bodyweight_default": bool(safe_get(row, "uses_bodyweight_default", False)),
    "primary_muscles": primary,
    "secondary_muscles": secondary,
    "instructions": instructions,
    "images": images,
  }


@anvil.server.callable
def search_exercise_options(query):
  return [serialize_exercise_option(r) for r in search_exercises_by_query(query, 30)]


@anvil.server.callable
def search_exercises_ui(query):
  rows = search_exercises_by_query(query, 30)
  return [serialize_exercise_option(r) for r in rows]


@anvil.server.callable
def get_exercise_detail(exercise_id):
  exercise = app_tables.exercises.get_by_id(exercise_id)
  if exercise is None:
    raise Exception("Exercise not found.")
  return serialize_exercise_detail(exercise)
