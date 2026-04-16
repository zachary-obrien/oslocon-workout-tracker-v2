import anvil.server
from anvil.tables import app_tables
from datetime import datetime, timezone, timedelta

from formatting_service import format_weight, format_share_datetime, normalize_for_match
from table_helpers import (
get_current_user,
get_recent_sessions,
get_all_sessions,
get_session_exercises_for_user_exercise,
get_session_exercises_for_slot,
get_session_exercises_for_session,
get_sets_for_session_exercise,
safe_get,
now,
)
from progression_service import apply_progression_after_workout


def _user_timezone(user):
  return (safe_get(user, "timezone", "America/Chicago") or "America/Chicago") if user else "America/Chicago"


def _session_tile_states(session):
  rows = get_session_exercises_for_session(session)
  return [safe_get(r, "tile_state", "gray") or "gray" for r in rows]


def _row_set_mode(row):
  return safe_get(row, "set_mode_snapshot", "standard") or "standard"


def _row_primary_muscles(row):
  muscles = safe_get(row, "primary_muscles_snapshot", None)
  if muscles:
    return list(muscles)
  exercise = safe_get(row, "exercise", None)
  return list(safe_get(exercise, "primary_muscles", []) or []) if exercise else []


def _row_secondary_muscles(row):
  muscles = safe_get(row, "secondary_muscles_snapshot", None)
  if muscles:
    return list(muscles)
  exercise = safe_get(row, "exercise", None)
  return list(safe_get(exercise, "secondary_muscles", []) or []) if exercise else []


def _session_exercise_exercise_id(row):
  exercise = safe_get(row, "exercise", None)
  return exercise.get_id() if exercise else None


def _serialize_session_exercise(row, timezone_name="America/Chicago"):
  session = safe_get(row, "workout_session", None)
  sets = get_sets_for_session_exercise(row)
  performed_sets = [s for s in sets if safe_get(s, "performed", False)]
  set_summaries = []
  for s in sets:
    performed = bool(safe_get(s, "performed", False))
    uses_bw = safe_get(s, "actual_uses_bodyweight", False) if performed else safe_get(s, "planned_uses_bodyweight", False)
    weight = safe_get(s, "actual_weight", None) if performed else safe_get(s, "planned_weight", None)
    reps = safe_get(s, "actual_reps", None) if performed else safe_get(s, "planned_reps", None)
    set_summaries.append({
      "performed": performed,
      "weight": format_weight(weight, uses_bw),
      "weight_value": weight,
      "uses_bodyweight": bool(uses_bw),
      "reps": reps,
    })

  strongest_e1rm = max([(safe_get(s, "estimated_1rm", 0) or 0) for s in performed_sets], default=0) or None
  strongest_score = max([(safe_get(s, "set_score", 0) or 0) for s in performed_sets], default=0) or None
  completed_at = safe_get(session, "completed_at", None) if session else safe_get(row, "created_at", None)

  return {
    "session_id": session.get_id() if session else None,
    "completed_at": completed_at,
    "completed_at_display": format_share_datetime(completed_at, timezone_name),
    "day_code": safe_get(session, "day_code_snapshot", "") if session else "",
    "exercise_id": _session_exercise_exercise_id(row),
    "exercise_name": safe_get(row, "exercise_name_snapshot", ""),
    "status": safe_get(row, "exercise_status", ""),
    "set_mode": _row_set_mode(row),
    "set_mode_label": {"standard": "Standard Sets", "myo_sets": "Myo Sets", "myo_rep_match": "Myo Rep Match Sets"}.get(_row_set_mode(row), "Standard Sets"),
    "tile_state": safe_get(row, "tile_state", "gray"),
    "planned_weight": safe_get(row, "planned_weight", None),
    "planned_reps": safe_get(row, "planned_reps", None),
    "planned_sets": safe_get(row, "planned_sets", None),
    "uses_bodyweight": bool(safe_get(row, "uses_bodyweight", False)),
    "share_text": safe_get(session, "share_text", "") if session else "",
    "tile_states": _session_tile_states(session) if session else [],
    "sets": set_summaries,
    "best_e1rm": strongest_e1rm,
    "best_set_score": strongest_score,
    "primary_muscles": _row_primary_muscles(row),
    "secondary_muscles": _row_secondary_muscles(row),
  }


def get_previous_session_summary(user, exercise):
  rows = get_session_exercises_for_user_exercise(user, exercise)
  if not rows:
    return None
  return _serialize_session_exercise(rows[0], _user_timezone(user))


def get_previous_slot_session_summary(user, slot):
  rows = get_session_exercises_for_slot(user, slot)
  if not rows:
    return None
  return _serialize_session_exercise(rows[0], _user_timezone(user))


def get_strongest_session_summary(user, exercise):
  rows = get_session_exercises_for_user_exercise(user, exercise)
  if not rows:
    return None

  def strength_key(r):
    sets = get_sets_for_session_exercise(r)
    e1rm = max([(safe_get(s, "estimated_1rm", 0) or 0) for s in sets], default=0)
    score = max([(safe_get(s, "set_score", 0) or 0) for s in sets], default=0)
    return (e1rm, score, safe_get(r, "created_at", now()) or now())

  best = max(rows, key=strength_key)
  return _serialize_session_exercise(best, _user_timezone(user))


def _active_slot_defaults(user, exercise):
  rows = [r for r in app_tables.workout_slots.search(user=user, exercise=exercise, is_active=True)]
  rows.sort(key=lambda r: ((safe_get(r, "display_order", 9999)), (safe_get(r, "slot_number", 9999))))
  if not rows:
    return None
  slot = rows[0]
  return {
    "weight": safe_get(slot, "base_target_weight", None),
    "reps": safe_get(slot, "base_target_reps", 12) or 12,
    "uses_bodyweight": bool(safe_get(slot, "uses_bodyweight", False)),
  }


def _rebuild_user_exercise_state(user, exercise):
  state = app_tables.user_exercise_state.get(user=user, exercise=exercise)
  if state is not None:
    state.delete()

  rows = [r for r in app_tables.workout_session_exercises.search(user=user, exercise=exercise)]
  rows.sort(key=lambda r: safe_get(r, "created_at", now()) or now())
  defaults = _active_slot_defaults(user, exercise)

  if not rows:
    if defaults is None:
      return
    app_tables.user_exercise_state.add_row(
      user=user,
      exercise=exercise,
      current_target_weight=defaults["weight"],
      current_target_reps=defaults["reps"],
      current_uses_bodyweight=defaults["uses_bodyweight"],
      qualifying_streak=0,
      last_completed_at=None,
      last_workout_session_exercise=None,
      strongest_estimated_1rm=None,
      strongest_set_score=None,
      updated_at=now(),
    )
    return

  first = rows[0]
  app_tables.user_exercise_state.add_row(
    user=user,
    exercise=exercise,
    current_target_weight=defaults["weight"] if defaults else safe_get(first, "planned_weight", None),
    current_target_reps=defaults["reps"] if defaults else (safe_get(first, "planned_reps", 12) or 12),
    current_uses_bodyweight=defaults["uses_bodyweight"] if defaults else bool(safe_get(first, "uses_bodyweight", False)),
    qualifying_streak=0,
    last_completed_at=None,
    last_workout_session_exercise=None,
    strongest_estimated_1rm=None,
    strongest_set_score=None,
    updated_at=now(),
  )

  for row in rows:
    if safe_get(row, "exercise_status", "") == "skipped":
      continue
    set_rows = get_sets_for_session_exercise(row)
    sets_payload = [
      {
        "planned_weight": safe_get(s, "planned_weight", None),
        "planned_reps": safe_get(s, "planned_reps", None),
        "planned_uses_bodyweight": safe_get(s, "planned_uses_bodyweight", False),
        "actual_weight": safe_get(s, "actual_weight", None),
        "actual_reps": safe_get(s, "actual_reps", None),
        "actual_uses_bodyweight": safe_get(s, "actual_uses_bodyweight", False),
        "performed": bool(safe_get(s, "performed", False)),
        "auto_completed": bool(safe_get(s, "auto_completed", False)),
        "set_index": safe_get(s, "set_index", 0),
      }
      for s in set_rows
    ]
    apply_progression_after_workout(
      user=user,
      exercise=exercise,
      group_size=safe_get(row, "group_size_snapshot", None) or safe_get(exercise, "group_size", "Small"),
      planned_weight=safe_get(row, "planned_weight", None),
      planned_reps=safe_get(row, "planned_reps", None),
      uses_bodyweight=bool(safe_get(row, "uses_bodyweight", False)),
      session_exercise_row=row,
      sets_payload=sets_payload,
    )


def _serialize_session_for_history(session, timezone_name):
  session_rows = get_session_exercises_for_session(session)
  primary = []
  secondary = []
  exercise_ids = []
  exercise_names = []
  muscle_groups = []
  set_modes = []
  for row in session_rows:
    exercise_id = _session_exercise_exercise_id(row)
    if exercise_id is not None:
      exercise_ids.append(exercise_id)
    name = safe_get(row, "exercise_name_snapshot", "")
    if name:
      exercise_names.append(name)
    mg = safe_get(row, "muscle_group_snapshot", "")
    if mg:
      muscle_groups.append(mg)
    for m in _row_primary_muscles(row):
      if m not in primary:
        primary.append(m)
    for m in _row_secondary_muscles(row):
      if m not in secondary:
        secondary.append(m)
    mode = _row_set_mode(row)
    if mode and mode not in set_modes:
      set_modes.append(mode)
  return {
    "session_id": session.get_id(),
    "completed_at": safe_get(session, "completed_at", None),
    "completed_at_display": format_share_datetime(safe_get(session, "completed_at", None), timezone_name),
    "day_code": safe_get(session, "day_code_snapshot", ""),
    "completion_bucket": safe_get(session, "completion_bucket", "standard"),
    "share_text": safe_get(session, "share_text", ""),
    "tile_states": _session_tile_states(session),
    "exercise_ids": exercise_ids,
    "exercise_names": exercise_names,
    "muscle_groups": muscle_groups,
    "primary_muscles": primary,
    "secondary_muscles": secondary,
    "set_modes": set_modes,
  }


@anvil.server.callable
def get_recent_history(limit=60):
  user = get_current_user()
  timezone_name = _user_timezone(user)
  sessions = get_recent_sessions(user, limit=limit)
  return [_serialize_session_for_history(s, timezone_name) for s in sessions]


@anvil.server.callable
def get_exercise_history(exercise_id):
  user = get_current_user()
  exercise = app_tables.exercises.get_by_id(exercise_id)
  if exercise is None:
    return []
  rows = get_session_exercises_for_user_exercise(user, exercise)
  return [_serialize_session_exercise(r, _user_timezone(user)) for r in rows[:100]]


def _coerce_reference_datetime(reference_dt):
  if not isinstance(reference_dt, datetime):
    reference_dt = now()
  if reference_dt.tzinfo is None or reference_dt.utcoffset() is None:
    return reference_dt.replace(tzinfo=timezone.utc)
  return reference_dt


def _week_bounds(reference_dt):
  reference_dt = _coerce_reference_datetime(reference_dt)
  weekday = reference_dt.weekday()  # Monday = 0
  start = datetime(
    reference_dt.year,
    reference_dt.month,
    reference_dt.day,
    tzinfo=reference_dt.tzinfo,
  ) - timedelta(days=weekday)
  end = start + timedelta(days=7)
  return start, end


def get_weekly_muscle_volume(user, reference_dt=None):
  start, end = _week_bounds(reference_dt or now())
  totals = {}
  sessions = get_all_sessions(user)
  for session in sessions:
    completed_at = safe_get(session, "completed_at", None)
    if completed_at is None:
      continue
    if completed_at.tzinfo is None or completed_at.utcoffset() is None:
      completed_at = completed_at.replace(tzinfo=start.tzinfo or timezone.utc)
    else:
      completed_at = completed_at.astimezone(start.tzinfo or timezone.utc)
    if completed_at < start or completed_at >= end:
      continue
    for row in get_session_exercises_for_session(session):
      performed_sets = [s for s in get_sets_for_session_exercise(row) if safe_get(s, "performed", False)]
      if not performed_sets:
        continue
      set_count = len(performed_sets)
      for muscle in _row_primary_muscles(row):
        key = str(muscle or "").strip()
        if not key:
          continue
        totals[key] = totals.get(key, 0.0) + float(set_count)
      for muscle in _row_secondary_muscles(row):
        key = str(muscle or "").strip()
        if not key:
          continue
        totals[key] = totals.get(key, 0.0) + float(set_count) * 0.5
  ordered = sorted(totals.items(), key=lambda item: (-item[1], normalize_for_match(item[0])))
  return {
    "week_start": start,
    "week_end": end,
    "muscles": [{"name": name, "weighted_sets": round(value, 1)} for name, value in ordered],
  }


def _delete_history_session_impl(session):
  user = safe_get(session, "user", None)
  session_rows = get_session_exercises_for_session(session)
  affected_exercises = []
  for row in session_rows:
    exercise = safe_get(row, "exercise", None)
    if exercise is not None and exercise not in affected_exercises:
      affected_exercises.append(exercise)
    for set_row in get_sets_for_session_exercise(row):
      set_row.delete()
    row.delete()
  session.delete()

  for exercise in affected_exercises:
    _rebuild_user_exercise_state(user, exercise)


@anvil.server.background_task
def delete_history_session_task(session_id):
  session = app_tables.workout_sessions.get_by_id(session_id)
  if session is None:
    return {"deleted": False}
  _delete_history_session_impl(session)
  return {"deleted": True}


@anvil.server.callable
def delete_history_session(session_id, selected_day_code=None):
  user = get_current_user()
  session = app_tables.workout_sessions.get_by_id(session_id)
  if session is None or safe_get(session, "user", None) != user:
    raise Exception("Workout history entry not found.")

  task = anvil.server.launch_background_task("delete_history_session_task", session_id)
  return {"queued": True, "task_id": task.get_id()}


@anvil.server.callable
def get_muscle_history(muscle_name):
  user = get_current_user()
  target = str(muscle_name or "").strip()
  if not target:
    return []
  rows = [r for r in app_tables.workout_session_exercises.search(user=user)]
  matched = []
  for row in rows:
    primary = _row_primary_muscles(row)
    secondary = _row_secondary_muscles(row)
    if target in primary or target in secondary:
      matched.append(_serialize_session_exercise(row, _user_timezone(user)))
  matched.sort(key=lambda x: x.get("completed_at") or datetime(1970,1,1,tzinfo=timezone.utc), reverse=True)
  return matched
