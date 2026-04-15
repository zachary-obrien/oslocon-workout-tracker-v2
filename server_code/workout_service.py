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
safe_get,
now,
get_workout_draft,
upsert_workout_draft,
clear_workout_draft as clear_workout_draft_row,
draft_is_fresh,
)
from progression_service import (
get_current_targets,
apply_progression_after_workout,
estimate_1rm,
compute_set_score,
)
from history_service import get_previous_session_summary, get_strongest_session_summary, get_weekly_muscle_volume
from quote_service import get_rotated_message
from routine_service import add_empty_slot, add_workout_day as add_day_impl, remove_workout_day as remove_day_impl, move_slot as move_slot_impl, remove_slot as remove_slot_impl


SET_MODES = {
  "standard": "Standard Sets",
  "myo_sets": "Myo Sets",
  "myo_rep_match": "Myo Rep Match Sets",
}


def _normalize_set_mode(mode):
  raw = str(mode or "standard").strip().lower().replace("-", "_").replace(" ", "_")
  if raw in SET_MODES:
    return raw
  return "standard"


def _serialize_day_options(days):
  return [{"day_code": safe_get(d, "day_code", ""), "display_order": safe_get(d, "display_order", None)} for d in days]


def _get_next_scheduled_day(user):
  days = get_active_days(user)
  if not days:
    return None
  sessions = get_recent_sessions(user, limit=1)
  if not sessions:
    return days[0]
  last_day_code = safe_get(sessions[0], "day_code_snapshot", None)
  current_index = next((i for i, d in enumerate(days) if safe_get(d, "day_code", None) == last_day_code), -1)
  next_index = (current_index + 1) % len(days)
  return days[next_index]


def _get_primary_muscle(exercise):
  muscles = safe_get(exercise, "primary_muscles", []) or []
  return muscles[0] if muscles else "General"


def _user_timezone(user):
  return (safe_get(user, "timezone", "America/Chicago") or "America/Chicago") if user else "America/Chicago"


def _slot_set_mode(slot):
  return _normalize_set_mode(safe_get(slot, "set_mode", "standard"))


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
    row_name = safe_get(row, "name", "") or ""
    row_normalized = safe_get(row, "normalized_name", None) or row_name
    if normalize_for_match(row_name) == target or normalize_for_match(row_normalized) == target:
      return row

  return None



def _normalize_exercise_identifier(value):
  if value in (None, ''):
    return ''
  if isinstance(value, (list, tuple)):
    return '|'.join(str(v).strip() for v in value)
  raw = str(value).strip()
  if not raw:
    return ''
  if raw.startswith('[') and raw.endswith(']'):
    inner = raw[1:-1].strip()
    parts = [p.strip().strip("'\"") for p in inner.split(',') if p.strip()]
    if parts:
      return '|'.join(parts)
  if raw.startswith('(') and raw.endswith(')'):
    inner = raw[1:-1].strip()
    parts = [p.strip().strip("'\"") for p in inner.split(',') if p.strip()]
    if parts:
      return '|'.join(parts)
  return raw

def _serialize_draft_payload(workout_payload):
  return {
    "current_day": workout_payload.get("current_day"),
    "saved_at": now().isoformat(),
    "exercises": [
      {
        "slot_number": ex.get("slot_number"),
        "exercise_id": ex.get("exercise_id"),
        "status": ex.get("status"),
        "collapsed": ex.get("collapsed"),
        "set_mode": ex.get("set_mode") or "standard",
        "sets": [
          {
            "set_index": s.get("set_index") or idx + 1,
            "weight": s.get("weight"),
            "reps": s.get("reps"),
            "performed": bool(s.get("performed")),
            "auto_completed": bool(s.get("auto_completed")),
            "locked": bool(s.get("locked")),
          }
          for idx, s in enumerate(ex.get("sets") or [])
        ],
      }
      for ex in (workout_payload.get("exercises") or [])
    ],
  }


def _apply_draft_to_exercises(exercises, draft_payload):
  if not draft_payload:
    return False
  draft_exercises = draft_payload.get("exercises") or []
  if not draft_exercises:
    return False

  draft_by_slot = {str(ex.get("slot_number")): ex for ex in draft_exercises}
  applied = False

  for ex in exercises:
    saved = draft_by_slot.get(str(ex.get("slot_number")))
    if not saved or ex.get("is_unassigned"):
      continue

    saved_id = _normalize_exercise_identifier(saved.get("exercise_id"))
    current_id = _normalize_exercise_identifier(ex.get("exercise_id"))
    if saved_id and current_id and saved_id != current_id:
      continue

    if saved.get("set_mode"):
      ex["set_mode"] = _normalize_set_mode(saved.get("set_mode"))
      ex["set_mode_label"] = SET_MODES[ex["set_mode"]]

    saved_sets = saved.get("sets") or []
    current_sets = list(ex.get("sets") or [])
    merged_sets = []
    for idx, s in enumerate(saved_sets):
      base = current_sets[idx] if idx < len(current_sets) else {}
      merged_sets.append({
        **base,
        "set_index": s.get("set_index") or idx + 1,
        "weight": s.get("weight"),
        "reps": s.get("reps"),
        "performed": bool(s.get("performed")),
        "auto_completed": bool(s.get("auto_completed")),
        "locked": bool(s.get("locked")),
      })
    if merged_sets:
      ex["sets"] = merged_sets
    else:
      ex["sets"] = current_sets

    ex["status"] = saved.get("status") or ex.get("status")
    if saved.get("collapsed") is not None:
      ex["collapsed"] = saved.get("collapsed")
    applied = True

  return applied


def _make_default_sets(target_weight, target_reps, uses_bodyweight, default_sets, set_mode):
  set_mode = _normalize_set_mode(set_mode)
  sets = []
  default_sets = int(default_sets or 0)
  for idx in range(default_sets):
    reps = target_reps
    locked = False
    if set_mode == "myo_sets" and idx >= 1:
      reps = 5
    if set_mode == "myo_rep_match" and idx >= 1:
      locked = True
    sets.append({
      "set_index": idx + 1,
      "weight": target_weight,
      "reps": reps,
      "performed": False,
      "auto_completed": False,
      "locked": locked,
    })
  return sets


def _serialize_slot(user, slot, day_slots):
  exercise = safe_get(slot, "exercise", None)
  display_order_index = day_slots.index(slot)
  can_move_up = display_order_index > 0
  can_move_down = display_order_index < len(day_slots) - 1
  set_mode = _slot_set_mode(slot)

  if exercise is None:
    return {
      "slot_number": safe_get(slot, "slot_number", None),
      "display_order": safe_get(slot, "display_order", None),
      "exercise_id": None,
      "exercise_name": "",
      "exercise_label": "Select exercise",
      "muscle_group": "Unassigned",
      "group_size": "Small",
      "base_target_weight": safe_get(slot, "base_target_weight", None),
      "base_target_reps": safe_get(slot, "base_target_reps", 12),
      "default_sets": safe_get(slot, "default_sets", 5),
      "uses_bodyweight": bool(safe_get(slot, "uses_bodyweight", False)),
      "recommended_weight": safe_get(slot, "base_target_weight", None),
      "recommended_reps": safe_get(slot, "base_target_reps", 12),
      "status": "active",
      "collapsed": False,
      "is_unassigned": True,
      "can_move_up": can_move_up,
      "can_move_down": can_move_down,
      "set_mode": set_mode,
      "set_mode_label": SET_MODES[set_mode],
      "sets": [],
      "previous_session": None,
      "strongest_day": None,
      "qualifying_progress": None,
    }

  targets = get_current_targets(
    user=user,
    exercise=exercise,
    default_weight=safe_get(slot, "base_target_weight", None),
    default_reps=safe_get(slot, "base_target_reps", 12),
    uses_bodyweight=bool(safe_get(slot, "uses_bodyweight", False)),
  )
  state = get_user_exercise_state(user, exercise)
  previous = get_previous_session_summary(user, exercise)
  strongest = get_strongest_session_summary(user, exercise)
  last_sets = list((previous or {}).get("sets") or [])
  performed_sets = [s for s in last_sets if s.get("performed")]
  seed_set = (performed_sets or last_sets or [None])[0]
  if seed_set:
    seeded_weight = seed_set.get("weight_value", seed_set.get("weight"))
    seeded_reps = seed_set.get("reps")
    if seeded_weight is not None or bool(safe_get(slot, "uses_bodyweight", False)):
      targets["weight"] = seeded_weight if not bool(safe_get(slot, "uses_bodyweight", False)) else 'BW'
    if seeded_reps not in (None, ""):
      targets["reps"] = int(seeded_reps)
  return {
    "slot_number": safe_get(slot, "slot_number", None),
    "display_order": safe_get(slot, "display_order", None),
    "exercise_id": exercise.get_id(),
    "exercise_name": safe_get(exercise, "name", ""),
    "exercise_label": safe_get(exercise, "name", ""),
    "muscle_group": _get_primary_muscle(exercise),
    "group_size": safe_get(exercise, "group_size", "Small"),
    "base_target_weight": safe_get(slot, "base_target_weight", None),
    "base_target_reps": safe_get(slot, "base_target_reps", 12),
    "default_sets": safe_get(slot, "default_sets", 5),
    "uses_bodyweight": bool(safe_get(slot, "uses_bodyweight", False)),
    "recommended_weight": targets["weight"],
    "recommended_reps": targets["reps"],
    "status": "active",
    "collapsed": False,
    "is_unassigned": False,
    "can_move_up": can_move_up,
    "can_move_down": can_move_down,
    "set_mode": set_mode,
    "set_mode_label": SET_MODES[set_mode],
    "sets": _make_default_sets(targets["weight"], targets["reps"], bool(safe_get(slot, "uses_bodyweight", False)), safe_get(slot, "default_sets", 5), set_mode),
    "previous_session": previous,
    "strongest_day": strongest,
    "qualifying_progress": {
      "current": int(safe_get(state, "qualifying_streak", 0) or 0) if state else 0,
      "target": int(safe_get(user, "progress_every_n_qualifying_workouts", 3) or 3),
    },
  }


def build_workout_payload(user, selected_day_code=None):
  days = get_active_days(user)
  if not days:
    return {"day_options": [], "exercises": [], "current_day": None, "next_scheduled_day": None}

  next_day = _get_next_scheduled_day(user)
  current_day = get_day_by_code(user, selected_day_code) if selected_day_code else next_day or days[0]
  if current_day is None:
    current_day = days[0]

  day_slots = get_slots_for_day(user, current_day)
  exercises = [_serialize_slot(user, slot, day_slots) for slot in day_slots]

  draft_row = get_workout_draft(user, current_day)
  resumed = False
  resumed_at = None
  if draft_is_fresh(draft_row, 24):
    resumed = _apply_draft_to_exercises(exercises, safe_get(draft_row, 'draft_payload', {}) or {})
    if resumed:
      resumed_at = safe_get(draft_row, 'updated_at', None) or safe_get(draft_row, 'created_at', None)

  return {
    "resolvedUser": {
      "display_name": safe_get(user, "display_name", "") or safe_get(user, "email", "user").split("@")[0].title(),
      "email": safe_get(user, "email", ""),
    },
    "current_day": safe_get(current_day, "day_code", None),
    "next_scheduled_day": safe_get(next_day, "day_code", None) if next_day else safe_get(current_day, "day_code", None),
    "day_options": _serialize_day_options(days),
    "can_remove_current_day": len(days) > 1,
    "exercises": exercises,
    "progression_settings": {
      "progress_every_n_qualifying_workouts": int(safe_get(user, "progress_every_n_qualifying_workouts", 3) or 3)
    },
    "draft_state": {
      "has_draft": resumed,
      "updated_at": resumed_at.isoformat() if resumed_at else "",
    },
  }


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
def save_workout_draft(day_code, draft_payload):
  user = get_current_user()
  day = get_day_by_code(user, day_code)
  if day is None:
    raise Exception("Workout day not found.")
  upsert_workout_draft(user, day, _serialize_draft_payload(draft_payload or {}))
  draft_row = get_workout_draft(user, day)
  updated = safe_get(draft_row, "updated_at", None) if draft_row else None
  return {"ok": True, "updated_at": updated.isoformat() if updated else ""}


@anvil.server.callable
def clear_current_workout_changes(day_code):
  user = get_current_user()
  day = get_day_by_code(user, day_code)
  if day is None:
    raise Exception("Workout day not found.")
  clear_workout_draft_row(user, day)
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
  update_kwargs = {
    "exercise": exercise,
    "uses_bodyweight": bool(safe_get(exercise, "uses_bodyweight_default", False)),
    "updated_at": now(),
  }
  slot.update(**update_kwargs)
  return build_workout_payload(user, day_code)


@anvil.server.callable
def set_exercise_set_mode(day_code, slot_number, mode):
  user = get_current_user()
  _, slot = _get_slot_by_identifiers(user, day_code, slot_number)
  slot.update(set_mode=_normalize_set_mode(mode), updated_at=now())
  return build_workout_payload(user, day_code)


@anvil.server.callable
def add_workout_day():
  user = get_current_user()
  day = add_day_impl(user)
  return build_workout_payload(user, safe_get(day, "day_code", None))


@anvil.server.callable
def remove_workout_day(day_code):
  user = get_current_user()
  remaining = remove_day_impl(user, day_code)
  new_day_code = safe_get(remaining[0], "day_code", None) if remaining else None
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
  weekly_volume = get_weekly_muscle_volume(user, completed_at)
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
    "weekly_volume": {
      "week_start": format_share_datetime(weekly_volume.get("week_start"), timezone_name).split(" ")[0] if weekly_volume.get("week_start") else "",
      "week_end": format_share_datetime(weekly_volume.get("week_end"), timezone_name).split(" ")[0] if weekly_volume.get("week_end") else "",
      "muscles": weekly_volume.get("muscles", []),
    },
  }


def _add_session_exercise_row(**kwargs):
  try:
    return app_tables.workout_session_exercises.add_row(**kwargs)
  except Exception:
    fallback = dict(kwargs)
    for key in ["set_mode_snapshot", "primary_muscles_snapshot", "secondary_muscles_snapshot"]:
      fallback.pop(key, None)
    row = app_tables.workout_session_exercises.add_row(**fallback)
    for key in ["set_mode_snapshot", "primary_muscles_snapshot", "secondary_muscles_snapshot"]:
      value = kwargs.get(key)
      if value is None:
        continue
      try:
        row[key] = value
      except Exception:
        pass
    return row


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
    exercise = _lookup_exercise_reference(ex.get("exercise_id"))
    if slot is None or exercise is None:
      continue

    previous_slot_rows = [r for r in app_tables.workout_session_exercises.search(user=user, workout_slot=slot)]
    previous_slot_rows.sort(key=lambda r: safe_get(r, "created_at", now()) or now(), reverse=True)
    previous_slot = previous_slot_rows[0] if previous_slot_rows else None
    exercise_changed = bool(previous_slot and safe_get(previous_slot, "exercise", None) != exercise)

    uses_bodyweight = bool(ex.get("uses_bodyweight"))
    recommended_weight = _coerce_weight(ex.get("recommended_weight"), uses_bodyweight)
    recommended_reps = _coerce_reps(ex.get("recommended_reps"))
    planned_sets = len(ex.get("sets", []))
    set_mode = _normalize_set_mode(ex.get("set_mode") or safe_get(slot, "set_mode", "standard"))

    sets_payload = []
    for idx, s in enumerate(ex.get("sets", []), start=1):
      planned_weight = _coerce_weight(s.get("weight"), uses_bodyweight)
      planned_reps = _coerce_reps(s.get("reps"))
      actual_weight = planned_weight if s.get("performed") else _coerce_weight(s.get("weight"), uses_bodyweight)
      actual_reps = planned_reps if s.get("performed") else _coerce_reps(s.get("reps"))
      sets_payload.append({
        "planned_weight": planned_weight,
        "planned_reps": planned_reps,
        "planned_uses_bodyweight": uses_bodyweight,
        "actual_weight": actual_weight,
        "actual_reps": actual_reps,
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

    session_exercise = _add_session_exercise_row(
      workout_session=session,
      user=user,
      workout_slot=slot,
      exercise=exercise,
      exercise_name_snapshot=safe_get(exercise, "name", ""),
      muscle_group_snapshot=(safe_get(exercise, "primary_muscles", []) or ["General"])[0],
      group_size_snapshot=safe_get(exercise, "group_size", "Small"),
      display_order_snapshot=safe_get(slot, "display_order", None),
      planned_weight=recommended_weight,
      planned_reps=recommended_reps,
      planned_sets=planned_sets,
      uses_bodyweight=uses_bodyweight,
      exercise_status=exercise_status,
      tile_state=tile_state,
      exercise_changed=exercise_changed,
      exceeded_plan=exceeded_plan,
      had_skipped_sets=had_skipped_sets,
      created_at=completed_at,
      set_mode_snapshot=set_mode,
      primary_muscles_snapshot=safe_get(exercise, "primary_muscles", []) or [],
      secondary_muscles_snapshot=safe_get(exercise, "secondary_muscles", []) or [],
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
        group_size=safe_get(exercise, "group_size", "Small"),
        planned_weight=recommended_weight,
        planned_reps=recommended_reps,
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

  clear_workout_draft_row(user, day)
  next_payload = build_workout_payload(user, None)
  return {"workout": next_payload, "completion_summary": summary, "completed_day_code": day_code}
