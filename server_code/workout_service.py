import anvil.server
from anvil.tables import app_tables

from formatting_service import format_share_datetime, tile_to_emoji, normalize_for_match
from table_helpers import (
get_current_user,
get_active_days,
get_day_by_code,
get_slots_for_day,
get_recent_sessions,
get_user_exercise_state,
get_workout_draft,
upsert_workout_draft,
clear_workout_draft,
now,
)
from progression_service import (
get_current_targets,
apply_progression_after_workout,
estimate_1rm,
compute_set_score,
)
from history_service import get_previous_session_summary, get_strongest_session_summary
from quote_service import get_rotated_message
from routine_service import add_empty_slot, add_workout_day as add_day_impl, remove_workout_day as remove_day_impl, move_slot as move_slot_impl, remove_slot as remove_slot_impl


def _serialize_day_options(days):
  return [{"day_code": d["day_code"], "display_order": d["display_order"]} for d in days]


def _get_next_scheduled_day(user):
  days = get_active_days(user)
  if not days:
    return None
  sessions = get_recent_sessions(user, limit=1)
  if not sessions:
    return days[0]
  last_day_code = sessions[0]["day_code_snapshot"]
  current_index = next((i for i, d in enumerate(days) if d["day_code"] == last_day_code), -1)
  next_index = (current_index + 1) % len(days)
  return days[next_index]


def _get_primary_muscle(exercise):
  muscles = exercise["primary_muscles"] or []
  return muscles[0] if muscles else "General"


def _user_timezone(user):
  return (user["timezone"] or "America/Chicago") if user else "America/Chicago"


def _coerce_number(value):
  if value in (None, "", False):
    return None
  if isinstance(value, (int, float)):
    return float(value)
  text = str(value).strip()
  if not text or text.lower() == 'bw':
    return None
  try:
    return float(text)
  except Exception:
    return None


def _coerce_weight(value, uses_bodyweight):
  if uses_bodyweight:
    return None
  return _coerce_number(value)


def _coerce_reps(value):
  num = _coerce_number(value)
  return int(num) if num is not None else None


def _same_numeric(a, b):
  na = _coerce_number(a)
  nb = _coerce_number(b)
  if na is None and nb is None:
    return True
  if na is None or nb is None:
    return False
  return abs(na - nb) < 1e-9


def _lookup_exercise_reference(exercise_ref):
  candidates = [exercise_ref]
  if isinstance(exercise_ref, str):
    stripped = exercise_ref.strip()
    if stripped not in candidates:
      candidates.append(stripped)
    if stripped.isdigit():
      candidates.append(int(stripped))

  for candidate in candidates:
    try:
      exercise = app_tables.exercises.get_by_id(candidate)
    except Exception:
      exercise = None
    if exercise is not None:
      return exercise

  raw = str(exercise_ref or '').strip()
  if not raw:
    return None

  target = normalize_for_match(raw)
  for row in app_tables.exercises.search(is_active=True):
    row_name = row["name"] or ""
    row_normalized = row["normalized_name"] or row_name
    if normalize_for_match(row_name) == target or normalize_for_match(row_normalized) == target:
      return row

  return None


def _serialize_draft_state(draft_row):
  if draft_row is None:
    return {"has_draft": False, "updated_at": None}
  return {
    "has_draft": True,
    "updated_at": draft_row["updated_at"],
  }


def _normalize_set_from_draft(item, fallback_index):
  return {
    "set_index": int(item.get("set_index") or fallback_index),
    "weight": item.get("weight"),
    "reps": item.get("reps"),
    "performed": bool(item.get("performed")),
    "auto_completed": bool(item.get("auto_completed")),
  }


def _apply_draft_to_payload(payload, draft_row):
  if draft_row is None:
    payload["draft_state"] = _serialize_draft_state(None)
    return payload

  draft = draft_row["draft_payload"] or {}
  saved_exercises = draft.get("exercises") or []
  saved_by_slot = {str(ex.get("slot_number")): ex for ex in saved_exercises if ex.get("slot_number") is not None}

  for ex in payload.get("exercises", []):
    saved = saved_by_slot.get(str(ex.get("slot_number")))
    if not saved or ex.get("is_unassigned"):
      continue
    saved_exercise_id = saved.get("exercise_id")
    if saved_exercise_id and ex.get("exercise_id") and str(saved_exercise_id) != str(ex.get("exercise_id")):
      continue
    if saved.get("recommended_weight") is not None:
      ex["recommended_weight"] = saved.get("recommended_weight")
    if saved.get("recommended_reps") is not None:
      ex["recommended_reps"] = saved.get("recommended_reps")
    if saved.get("status"):
      ex["status"] = saved.get("status")
    if "collapsed" in saved:
      ex["collapsed"] = saved.get("collapsed")
    saved_sets = list(saved.get("sets") or [])
    if saved_sets:
      merged = []
      base_sets = list(ex.get("sets") or [])
      max_len = max(len(base_sets), len(saved_sets))
      for idx in range(max_len):
        base = dict(base_sets[idx]) if idx < len(base_sets) else {"set_index": idx + 1}
        if idx < len(saved_sets):
          base.update(_normalize_set_from_draft(saved_sets[idx], idx + 1))
        else:
          base.setdefault("performed", False)
          base.setdefault("auto_completed", False)
        merged.append(base)
      ex["sets"] = merged

  payload["draft_state"] = _serialize_draft_state(draft_row)
  return payload


def _serialize_slot(user, slot, day_slots):
  exercise = slot["exercise"]
  display_order_index = day_slots.index(slot)
  can_move_up = display_order_index > 0
  can_move_down = display_order_index < len(day_slots) - 1

  if exercise is None:
    return {
      "slot_number": slot["slot_number"],
      "display_order": slot["display_order"],
      "exercise_id": None,
      "exercise_name": "",
      "exercise_label": "Select exercise",
      "muscle_group": "Unassigned",
      "group_size": "Small",
      "base_target_weight": slot["base_target_weight"],
      "base_target_reps": slot["base_target_reps"],
      "default_sets": slot["default_sets"],
      "uses_bodyweight": slot["uses_bodyweight"],
      "recommended_weight": slot["base_target_weight"],
      "recommended_reps": slot["base_target_reps"],
      "status": "active",
      "collapsed": False,
      "is_unassigned": True,
      "can_move_up": can_move_up,
      "can_move_down": can_move_down,
      "sets": [],
      "previous_session": None,
      "strongest_day": None,
      "qualifying_progress": None,
    }

  targets = get_current_targets(
    user=user,
    exercise=exercise,
    default_weight=slot["base_target_weight"],
    default_reps=slot["base_target_reps"],
    uses_bodyweight=slot["uses_bodyweight"],
  )
  state = get_user_exercise_state(user, exercise)
  previous = get_previous_session_summary(user, exercise)
  strongest = get_strongest_session_summary(user, exercise)
  return {
    "slot_number": slot["slot_number"],
    "display_order": slot["display_order"],
    "exercise_id": exercise.get_id(),
    "exercise_name": exercise["name"],
    "exercise_label": exercise["name"],
    "muscle_group": _get_primary_muscle(exercise),
    "group_size": exercise["group_size"],
    "base_target_weight": slot["base_target_weight"],
    "base_target_reps": slot["base_target_reps"],
    "default_sets": slot["default_sets"],
    "uses_bodyweight": slot["uses_bodyweight"],
    "recommended_weight": targets["weight"],
    "recommended_reps": targets["reps"],
    "status": "active",
    "collapsed": False,
    "is_unassigned": False,
    "can_move_up": can_move_up,
    "can_move_down": can_move_down,
    "sets": [
      {
        "set_index": idx + 1,
        "weight": targets["weight"],
        "reps": targets["reps"],
        "performed": False,
        "auto_completed": False,
      }
      for idx in range(int(slot["default_sets"] or 0))
    ],
    "previous_session": previous,
    "strongest_day": strongest,
    "qualifying_progress": {
      "current": int(state["qualifying_streak"] or 0) if state else 0,
      "target": int(user["progress_every_n_qualifying_workouts"] or 3),
    },
  }

def build_workout_payload(user, selected_day_code=None, apply_draft=True):
  days = get_active_days(user)
  if not days:
    return {"day_options": [], "exercises": [], "current_day": None, "next_scheduled_day": None}

  next_day = _get_next_scheduled_day(user)
  current_day = get_day_by_code(user, selected_day_code) if selected_day_code else next_day or days[0]
  if current_day is None:
    current_day = days[0]

  day_slots = get_slots_for_day(user, current_day)
  exercises = [_serialize_slot(user, slot, day_slots) for slot in day_slots]

  payload = {
    "resolvedUser": {
      "display_name": user["display_name"] or user["email"].split("@")[0].title(),
      "email": user["email"],
    },
    "current_day": current_day["day_code"],
    "next_scheduled_day": next_day["day_code"] if next_day else current_day["day_code"],
    "day_options": _serialize_day_options(days),
    "can_remove_current_day": len(days) > 1,
    "exercises": exercises,
    "progression_settings": {
      "progress_every_n_qualifying_workouts": int(user["progress_every_n_qualifying_workouts"] or 3)
    },
  }

  if apply_draft:
    draft_row = get_workout_draft(user, current_day)
    return _apply_draft_to_payload(payload, draft_row)

  payload["draft_state"] = _serialize_draft_state(None)
  return payload


def _get_slot_by_identifiers(user, day_code, slot_number):
  day = get_day_by_code(user, day_code)
  if day is None:
    raise Exception("Workout day not found.")
  slot = app_tables.workout_slots.get(user=user, workout_day=day, slot_number=slot_number, is_active=True)
  if slot is None:
    raise Exception("Workout slot not found.")
  return day, slot


@anvil.server.callable
def load_workout_day(day_code=None):
  user = get_current_user()
  return build_workout_payload(user, day_code)


@anvil.server.callable
def add_exercise_slot(day_code):
  user = get_current_user()
  day = get_day_by_code(user, day_code)
  add_empty_slot(user, day)
  return build_workout_payload(user, day_code)


@anvil.server.callable
def remove_exercise_slot(day_code, slot_number):
  user = get_current_user()
  day = get_day_by_code(user, day_code)
  remove_slot_impl(user, day, slot_number)
  return build_workout_payload(user, day_code)


@anvil.server.callable
def move_exercise_slot(day_code, slot_number, direction):
  user = get_current_user()
  day = get_day_by_code(user, day_code)
  move_slot_impl(user, day, slot_number, direction)
  return build_workout_payload(user, day_code)


@anvil.server.callable
def assign_slot_exercise(day_code, slot_number, exercise_id):
  user = get_current_user()
  _, slot = _get_slot_by_identifiers(user, day_code, slot_number)
  exercise = _lookup_exercise_reference(exercise_id)
  if exercise is None:
    raise Exception("Exercise not found.")
  slot.update(exercise=exercise, uses_bodyweight=bool(exercise["uses_bodyweight_default"]), updated_at=now())
  return build_workout_payload(user, day_code)


@anvil.server.callable
def add_workout_day():
  user = get_current_user()
  day = add_day_impl(user)
  return build_workout_payload(user, day["day_code"])


@anvil.server.callable
def remove_workout_day(day_code):
  user = get_current_user()
  remaining = remove_day_impl(user, day_code)
  new_day_code = remaining[0]["day_code"] if remaining else None
  return build_workout_payload(user, new_day_code)


@anvil.server.callable
def update_progression_setting(value):
  user = get_current_user()
  user["progress_every_n_qualifying_workouts"] = int(value or 3)
  return build_workout_payload(user, None)


def _classify_tile_state(exercise_changed, exercise_status, sets_payload):
  if exercise_status == "skipped":
    return "red"
  if any(not s.get("performed") for s in sets_payload):
    return "orange"
  if exercise_changed:
    return "gray"
  any_weight_changed = False
  any_reps_changed = False
  for s in sets_payload:
    if not s.get("performed"):
      continue
    if not _same_numeric(s.get("actual_weight"), s.get("planned_weight")):
      any_weight_changed = True
    if _coerce_reps(s.get("actual_reps")) != _coerce_reps(s.get("planned_reps")):
      any_reps_changed = True
  if any_weight_changed and any_reps_changed:
    return "gray"
  return "green"


def _exercise_exceeded(sets_payload, uses_bodyweight):
  for s in sets_payload:
    if not s.get("performed"):
      continue
    actual_reps = _coerce_reps(s.get("actual_reps")) or 0
    planned_reps = _coerce_reps(s.get("planned_reps")) or 0
    if actual_reps > planned_reps:
      return True
    if not uses_bodyweight:
      actual_weight = _coerce_weight(s.get("actual_weight"), False) or 0
      planned_weight = _coerce_weight(s.get("planned_weight"), False) or 0
      if actual_weight > planned_weight:
        return True
  return False


def _build_completion_summary(user, completion_bucket, tile_states, completed_at):
  session_count = len(get_recent_sessions(user, 10000))
  message = get_rotated_message(completion_bucket, session_count)
  timezone_name = _user_timezone(user)
  formatted_date = format_share_datetime(completed_at, timezone_name)
  share_text = "Oslocon Workout!\n" + formatted_date + "\n" + "".join(tile_to_emoji(t) for t in tile_states)
  return {
    "headline": {
      "skipped": "Workout logged",
      "standard": "Great work",
      "exceeded": "Outstanding work",
    }[completion_bucket],
    "message": message,
    "date": formatted_date,
    "tile_states": tile_states,
    "share_text": share_text,
    "show_confetti": completion_bucket in ("standard", "exceeded"),
    "bucket": completion_bucket,
  }




@anvil.server.callable
def save_workout_draft(day_code, draft_payload):
  user = get_current_user()
  day = get_day_by_code(user, day_code)
  if day is None:
    raise Exception("Workout day not found.")
  row = upsert_workout_draft(user, day, draft_payload or {})
  return {"updated_at": row["updated_at"], "has_draft": True}


@anvil.server.callable
def clear_current_workout_changes(day_code):
  user = get_current_user()
  day = get_day_by_code(user, day_code)
  if day is None:
    raise Exception("Workout day not found.")
  clear_workout_draft(user, day)
  return build_workout_payload(user, day_code, apply_draft=False)


@anvil.server.callable
def submit_workout(payload):
  user = get_current_user()
  day_code = payload["day_code"]
  day = get_day_by_code(user, day_code)
  exercises_payload = payload.get("exercises", [])
  completed_at = now()

  session = app_tables.workout_sessions.add_row(
    user=user,
    workout_day=day,
    day_code_snapshot=day_code,
    started_at=completed_at,
    completed_at=completed_at,
    completion_bucket="standard",
    share_text="",
    notes="",
  )

  tile_states = []
  any_exceeded = False
  any_skippedish = False

  for ex in exercises_payload:
    if not ex.get("exercise_id"):
      continue
    slot = app_tables.workout_slots.get(user=user, workout_day=day, slot_number=ex["slot_number"], is_active=True)
    exercise = app_tables.exercises.get_by_id(ex["exercise_id"])
    if slot is None or exercise is None:
      continue

    previous_slot_rows = [r for r in app_tables.workout_session_exercises.search(user=user, workout_slot=slot)]
    previous_slot_rows.sort(key=lambda r: r["created_at"] or now(), reverse=True)
    previous_slot = previous_slot_rows[0] if previous_slot_rows else None
    exercise_changed = bool(previous_slot and previous_slot["exercise"] != exercise)

    uses_bodyweight = bool(ex.get("uses_bodyweight"))
    planned_weight = _coerce_weight(ex.get("recommended_weight"), uses_bodyweight)
    planned_reps = _coerce_reps(ex.get("recommended_reps"))
    planned_sets = len(ex.get("sets", []))

    sets_payload = []
    for idx, s in enumerate(ex.get("sets", []), start=1):
      sets_payload.append({
        "planned_weight": planned_weight,
        "planned_reps": planned_reps,
        "planned_uses_bodyweight": uses_bodyweight,
        "actual_weight": _coerce_weight(s.get("weight"), uses_bodyweight),
        "actual_reps": _coerce_reps(s.get("reps")),
        "actual_uses_bodyweight": uses_bodyweight,
        "performed": bool(s.get("performed")),
        "auto_completed": bool(s.get("auto_completed")),
        "set_index": idx,
      })

    exercise_status = ex.get("status", "completed")
    tile_state = _classify_tile_state(exercise_changed, exercise_status, sets_payload)
    tile_states.append(tile_state)

    had_skipped_sets = any(not s["performed"] for s in sets_payload) and exercise_status != "skipped"
    exceeded_plan = _exercise_exceeded(sets_payload, uses_bodyweight)
    any_exceeded = any_exceeded or exceeded_plan
    any_skippedish = any_skippedish or exercise_status == "skipped" or had_skipped_sets

    session_exercise = app_tables.workout_session_exercises.add_row(
      workout_session=session,
      user=user,
      workout_slot=slot,
      exercise=exercise,
      exercise_name_snapshot=exercise["name"],
      muscle_group_snapshot=(exercise["primary_muscles"] or ["General"])[0],
      group_size_snapshot=exercise["group_size"],
      display_order_snapshot=slot["display_order"],
      planned_weight=planned_weight,
      planned_reps=planned_reps,
      planned_sets=planned_sets,
      uses_bodyweight=uses_bodyweight,
      exercise_status=exercise_status,
      tile_state=tile_state,
      exercise_changed=exercise_changed,
      exceeded_plan=exceeded_plan,
      had_skipped_sets=had_skipped_sets,
      created_at=completed_at,
    )

    for s in sets_payload:
      app_tables.workout_session_sets.add_row(
        workout_session_exercise=session_exercise,
        set_index=s["set_index"],
        planned_weight=s["planned_weight"],
        planned_reps=s["planned_reps"],
        planned_uses_bodyweight=s["planned_uses_bodyweight"],
        actual_weight=s["actual_weight"],
        actual_reps=s["actual_reps"],
        actual_uses_bodyweight=s["actual_uses_bodyweight"],
        performed=s["performed"],
        auto_completed=s["auto_completed"],
        estimated_1rm=estimate_1rm(s["actual_weight"], s["actual_reps"], uses_bodyweight) if s["performed"] else None,
        set_score=compute_set_score(s["actual_weight"], s["actual_reps"], uses_bodyweight) if s["performed"] else None,
      )

    if exercise_status != "skipped":
      apply_progression_after_workout(
        user=user,
        exercise=exercise,
        group_size=exercise["group_size"],
        planned_weight=planned_weight,
        planned_reps=planned_reps,
        uses_bodyweight=uses_bodyweight,
        session_exercise_row=session_exercise,
        sets_payload=sets_payload,
      )

  completion_bucket = "standard"
  if any_exceeded:
    completion_bucket = "exceeded"
  elif any_skippedish:
    completion_bucket = "skipped"

  summary = _build_completion_summary(user, completion_bucket, tile_states, completed_at)
  session["completion_bucket"] = completion_bucket
  session["share_text"] = summary["share_text"]

  clear_workout_draft(user, day)
  clear_workout_draft(user, day)
  next_payload = build_workout_payload(user, None)
  return {"workout": next_payload, "completion_summary": summary, "completed_day_code": day_code}
