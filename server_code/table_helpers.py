import anvil.users
from anvil.tables import app_tables
from datetime import datetime

from formatting_service import normalize_for_match


USER_DEFAULTS = {
  "display_name": "",
  "progress_every_n_qualifying_workouts": 3,
  "timezone": "America/Chicago",
  "role": "user",
  "is_admin": False,
  "onboarding_complete": False,
  "created_via": "google",
  "stripe_customer_id": "",
  "plan_tier": "free",
}


def now():
  return datetime.now()


def safe_get(row, key, default=None):
  try:
    value = row[key]
  except Exception:
    return default
  return default if value is None else value


def get_current_user(required=True):
  user = anvil.users.get_user()
  if required and user is None:
    raise Exception("User must be logged in.")
  return user


def ensure_user_defaults(user):
  changed = {}
  for key, default in USER_DEFAULTS.items():
    try:
      current = user[key]
    except Exception:
      current = None
    if current is None or current == "":
      changed[key] = default
  if changed:
    user.update(**changed)
  return user


def get_active_days(user):
  days = [r for r in app_tables.workout_days.search(user=user, is_active=True)]
  return sorted(days, key=lambda r: (safe_get(r, "display_order", 9999), safe_get(r, "day_code", "")))


def get_day_by_code(user, day_code):
  for row in get_active_days(user):
    if safe_get(row, "day_code") == day_code and safe_get(row, "is_active", False):
      return row
  return None


def get_slots_for_day(user, workout_day):
  slots = [
    r for r in app_tables.workout_slots.search(user=user, workout_day=workout_day, is_active=True)
  ]
  return sorted(slots, key=lambda r: (safe_get(r, "display_order", 9999), safe_get(r, "slot_number", 9999)))


def get_recent_sessions(user, limit=25):
  rows = [r for r in app_tables.workout_sessions.search(user=user)]
  rows.sort(key=lambda r: safe_get(r, "completed_at", now()) or now(), reverse=True)
  return rows[:limit]


def get_all_sessions(user):
  rows = [r for r in app_tables.workout_sessions.search(user=user)]
  rows.sort(key=lambda r: safe_get(r, "completed_at", now()) or now(), reverse=True)
  return rows


def get_session_exercises_for_user_exercise(user, exercise):
  rows = [r for r in app_tables.workout_session_exercises.search(user=user, exercise=exercise)]
  rows.sort(key=lambda r: safe_get(r, "created_at", now()) or now(), reverse=True)
  return rows


def get_session_exercises_for_slot(user, workout_slot):
  rows = [r for r in app_tables.workout_session_exercises.search(user=user, workout_slot=workout_slot)]
  rows.sort(key=lambda r: safe_get(r, "created_at", now()) or now(), reverse=True)
  return rows


def get_session_exercises_for_session(session):
  rows = [r for r in app_tables.workout_session_exercises.search(workout_session=session)]
  rows.sort(key=lambda r: (safe_get(r, "display_order_snapshot", 9999), safe_get(r, "created_at", now()) or now()))
  return rows


def get_sets_for_session_exercise(session_exercise):
  rows = [r for r in app_tables.workout_session_sets.search(workout_session_exercise=session_exercise)]
  rows.sort(key=lambda r: safe_get(r, "set_index", 0))
  return rows


def get_user_exercise_state(user, exercise):
  return app_tables.user_exercise_state.get(user=user, exercise=exercise)


def get_or_create_user_exercise_state(user, exercise, default_weight, default_reps, uses_bodyweight):
  row = get_user_exercise_state(user, exercise)
  if row:
    return row
  return app_tables.user_exercise_state.add_row(
    user=user,
    exercise=exercise,
    current_target_weight=default_weight,
    current_target_reps=default_reps,
    current_uses_bodyweight=uses_bodyweight,
    qualifying_streak=0,
    last_completed_at=None,
    last_workout_session_exercise=None,
    strongest_estimated_1rm=None,
    strongest_set_score=None,
    updated_at=now(),
  )


def search_exercises_by_query(query, limit=25):
  q = normalize_for_match(query)
  rows = list(app_tables.exercises.search(is_active=True))
  if not q:
    rows.sort(key=lambda r: safe_get(r, "name", "") or "")
    return rows[:limit]

  def score(row):
    name = normalize_for_match(safe_get(row, "name", ""))
    norm = normalize_for_match(safe_get(row, "normalized_name", None) or safe_get(row, "name", ""))
    if norm == q:
      return (0, len(name))
    if q in norm:
      return (1, len(name))
    return (2, len(name))

  filtered = [
    r for r in rows
    if q in normalize_for_match(safe_get(r, "name", "")) or q in normalize_for_match(safe_get(r, "normalized_name", None) or safe_get(r, "name", ""))
  ]
  filtered.sort(key=score)
  return filtered[:limit]


def get_exercise_images(exercise):
  rows = [r for r in app_tables.exercise_images.search(exercise=exercise)]
  rows.sort(key=lambda r: (safe_get(r, "sort_order", 9999), r.get_id()))
  return rows


def get_first_exercise_image(exercise):
  rows = get_exercise_images(exercise)
  return rows[0] if rows else None
