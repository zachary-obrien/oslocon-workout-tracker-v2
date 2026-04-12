import anvil.server
from anvil.tables import app_tables

from formatting_service import format_weight
from table_helpers import (
    get_current_user,
    get_recent_sessions,
    get_session_exercises_for_user_exercise,
    get_session_exercises_for_slot,
    get_sets_for_session_exercise,
    now,
)


def _serialize_session_exercise(row):
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

    return {
        "session_id": session.get_id() if session else None,
        "completed_at": session["completed_at"] if session else row["created_at"],
        "day_code": session["day_code_snapshot"] if session else "",
        "exercise_name": row["exercise_name_snapshot"],
        "status": row["exercise_status"],
        "tile_state": row["tile_state"],
        "planned_weight": row["planned_weight"],
        "planned_reps": row["planned_reps"],
        "planned_sets": row["planned_sets"],
        "uses_bodyweight": row["uses_bodyweight"],
        "sets": set_summaries,
        "best_e1rm": strongest_e1rm,
        "best_set_score": strongest_score,
    }


def get_previous_session_summary(user, exercise):
    rows = get_session_exercises_for_user_exercise(user, exercise)
    if not rows:
        return None
    return _serialize_session_exercise(rows[0])


def get_previous_slot_session_summary(user, slot):
    rows = get_session_exercises_for_slot(user, slot)
    if not rows:
        return None
    return _serialize_session_exercise(rows[0])


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
    return _serialize_session_exercise(best)


@anvil.server.callable
def get_recent_history(limit=20):
    user = get_current_user()
    sessions = get_recent_sessions(user, limit=limit)
    return [
        {
            "session_id": s.get_id(),
            "completed_at": s["completed_at"],
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
    return [_serialize_session_exercise(r) for r in rows[:15]]
