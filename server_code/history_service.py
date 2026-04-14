import anvil.server
from anvil.tables import app_tables

from formatting_service import format_weight, format_share_datetime
from table_helpers import (
get_current_user,
get_recent_sessions,
get_session_exercises_for_user_exercise,
get_session_exercises_for_slot,
get_sets_for_session_exercise,
now,
)
from progression_service import apply_progression_after_workout


def _user_timezone(user):
  return (user["timezone"] or "America/Chicago") if user else "America/Chicago"


def _lookup_session_by_id(session_id):
  candidates = [session_id]
  if isinstance(session_id, str):
    stripped = session_id.strip()
    if stripped not in candidates:
      candidates.append(stripped)
    if stripped.isdigit():
      candidates.append(int(stripped))
  for candidate in candidates:
    try:
      session = app_tables.workout_sessions.get_by_id(candidate)
    except Exception:
      session = None
    if session is not None:
      return session
  return None


def _serialize_session_exercise(row, timezone_name="America/Chicago"):
  session = row["workout_session"]
  sets = get_sets_for_session_exercise(row)
  performed_sets = [s for s in sets if s["performed"]]
  set_summaries = []
  for s in sets:
    uses_bw = s["actual_uses_bodyweight"] if s["performed"] else s["planned_uses_bodyweight"]
    weight = s["actual_weight"] if s["performed"] else s["planned_weight"]
    reps = s["actual_reps"] if s["performed"] else s["planned_reps"]
    set_summaries.append({
      "performed": bool(s["performed"]),
      "weight": format_weight(weight, uses_bw),
      "reps": reps,
    })

  strongest_e1rm = max([(s["estimated_1rm"] or 0) for s in performed_sets], default=0) or None
  strongest_score = max([(s["set_score"] or 0) for s in performed_sets], default=0) or None
  completed_at = session["completed_at"] if session else row["created_at"]

  return {
    "session_id": session.get_id() if session else None,
    "completed_at": completed_at,
    "completed_at_display": format_share_datetime(completed_at, timezone_name),
    "day_code": session["day_code_snapshot"] if session else "",
    "exercise_name": row["exercise_name_snapshot"],
    "status": row["exercise_status"],
    "tile_state": row["tile_state"],
    "planned_weight": row["planned_weight"],
    "planned_reps": row["planned_reps"],
    "planned_sets": row["planned_sets"],
    "uses_bodyweight": row["uses_bodyweight"],
    "share_text": session["share_text"] if session else "",
    "sets": set_summaries,
    "best_e1rm": strongest_e1rm,
    "best_set_score": strongest_score,
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
    e1rm = max([(s["estimated_1rm"] or 0) for s in sets], default=0)
    score = max([(s["set_score"] or 0) for s in sets], default=0)
    return (e1rm, score, r["created_at"] or now())

  best = max(rows, key=strength_key)
  return _serialize_session_exercise(best, _user_timezone(user))


def _active_slot_defaults(user, exercise):
  rows = [r for r in app_tables.workout_slots.search(user=user, exercise=exercise, is_active=True)]
  rows.sort(key=lambda r: ((r["display_order"] or 9999), (r["slot_number"] or 9999)))
  if not rows:
    return None
  slot = rows[0]
  return {
    "weight": slot["base_target_weight"],
    "reps": slot["base_target_reps"] or 12,
    "uses_bodyweight": bool(slot["uses_bodyweight"]),
  }


def _rebuild_user_exercise_state(user, exercise):
  state = app_tables.user_exercise_state.get(user=user, exercise=exercise)
  if state is not None:
    state.delete()

  rows = [r for r in app_tables.workout_session_exercises.search(user=user, exercise=exercise)]
  rows.sort(key=lambda r: r["created_at"] or now())
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
    current_target_weight=defaults["weight"] if defaults else first["planned_weight"],
    current_target_reps=defaults["reps"] if defaults else (first["planned_reps"] or 12),
    current_uses_bodyweight=defaults["uses_bodyweight"] if defaults else bool(first["uses_bodyweight"]),
    qualifying_streak=0,
    last_completed_at=None,
    last_workout_session_exercise=None,
    strongest_estimated_1rm=None,
    strongest_set_score=None,
    updated_at=now(),
  )

  for row in rows:
    if row["exercise_status"] == "skipped":
      continue
    set_rows = get_sets_for_session_exercise(row)
    sets_payload = [
      {
        "planned_weight": s["planned_weight"],
        "planned_reps": s["planned_reps"],
        "planned_uses_bodyweight": s["planned_uses_bodyweight"],
        "actual_weight": s["actual_weight"],
        "actual_reps": s["actual_reps"],
        "actual_uses_bodyweight": s["actual_uses_bodyweight"],
        "performed": bool(s["performed"]),
        "auto_completed": bool(s["auto_completed"]),
        "set_index": s["set_index"],
      }
      for s in set_rows
    ]
    apply_progression_after_workout(
      user=user,
      exercise=exercise,
      group_size=row["group_size_snapshot"] or exercise["group_size"],
      planned_weight=row["planned_weight"],
      planned_reps=row["planned_reps"],
      uses_bodyweight=bool(row["uses_bodyweight"]),
      session_exercise_row=row,
      sets_payload=sets_payload,
    )


@anvil.server.callable
def get_recent_history(limit=20):
  user = get_current_user()
  timezone_name = _user_timezone(user)
  sessions = get_recent_sessions(user, limit=limit)
  return [
    {
      "session_id": s.get_id(),
      "completed_at": s["completed_at"],
      "completed_at_display": format_share_datetime(s["completed_at"], timezone_name),
      "day_code": s["day_code_snapshot"],
      "completion_bucket": s["completion_bucket"],
      "share_text": s["share_text"],
    }
    for s in sessions
  ]


@anvil.server.callable
def get_exercise_history(exercise_id):
  user = get_current_user()
  exercise = app_tables.exercises.get_by_id(exercise_id)
  if exercise is None:
    return []
  rows = get_session_exercises_for_user_exercise(user, exercise)
  return [_serialize_session_exercise(r, _user_timezone(user)) for r in rows[:15]]


@anvil.server.callable
def delete_history_session(session_id, selected_day_code=None):
  user = get_current_user()
  session = _lookup_session_by_id(session_id)
  if session is None or session["user"] != user:
    raise Exception("Workout history entry not found.")

  session_rows = [r for r in app_tables.workout_session_exercises.search(workout_session=session)]
  affected_exercises = []
  for row in session_rows:
    exercise = row["exercise"]
    if exercise is not None and exercise not in affected_exercises:
      affected_exercises.append(exercise)
    for set_row in get_sets_for_session_exercise(row):
      set_row.delete()
    row.delete()
  session.delete()

  for exercise in affected_exercises:
    _rebuild_user_exercise_state(user, exercise)

  from workout_service import build_workout_payload
  return build_workout_payload(user, selected_day_code)
