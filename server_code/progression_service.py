from table_helpers import get_or_create_user_exercise_state, now


def get_increment(group_size):
    return 5 if (group_size or "").lower() == "large" else 2.5


def get_progress_target_count(user):
    return int(user["progress_every_n_qualifying_workouts"] or 3)


def get_current_targets(user, exercise, default_weight, default_reps, uses_bodyweight):
    state = get_or_create_user_exercise_state(user, exercise, default_weight, default_reps, uses_bodyweight)
    return {
        "weight": state["current_target_weight"],
        "reps": state["current_target_reps"],
        "uses_bodyweight": state["current_uses_bodyweight"],
        "qualifying_streak": state["qualifying_streak"] or 0,
    }


def _set_score(weight, reps, uses_bodyweight):
    if uses_bodyweight or weight is None:
        weight = 0
    return (float(weight) if weight is not None else 0) * (int(reps or 0))


def _estimate_1rm(weight, reps, uses_bodyweight):
    if uses_bodyweight or weight is None:
        return None
    reps = int(reps or 0)
    try:
        weight = float(weight)
    except Exception:
        return None
    if reps <= 0:
        return None
    return round(weight * (1 + reps / 30.0), 2)


def evaluate_qualifying(planned_weight, planned_reps, uses_bodyweight, sets_payload):
    if not sets_payload:
        return False
    if len([s for s in sets_payload if s.get("performed")]) != len(sets_payload):
        return False
    for s in sets_payload:
        actual_reps = int(s.get("actual_reps") or 0)
        if actual_reps < int(planned_reps or 0):
            return False
        if not uses_bodyweight:
            actual_weight = float(s.get("actual_weight") or 0)
            planned = float(planned_weight or 0)
            if actual_weight < planned:
                return False
    return True


def apply_progression_after_workout(user, exercise, group_size, planned_weight, planned_reps, uses_bodyweight, session_exercise_row, sets_payload):
    state = get_or_create_user_exercise_state(user, exercise, planned_weight, planned_reps, uses_bodyweight)
    qualifies = evaluate_qualifying(planned_weight, planned_reps, uses_bodyweight, sets_payload)
    streak = int(state["qualifying_streak"] or 0)

    if qualifies:
        streak += 1
    else:
        streak = 0

    target_count = get_progress_target_count(user)
    next_weight = state["current_target_weight"] if state["current_target_weight"] is not None else planned_weight
    next_reps = state["current_target_reps"] or planned_reps
    next_bw = bool(state["current_uses_bodyweight"])

    if qualifies and not uses_bodyweight and streak >= target_count:
        next_weight = float(next_weight or 0) + get_increment(group_size)
        streak = 0

    best_e1rm = None
    best_score = None
    for s in sets_payload:
        if not s.get("performed"):
            continue
        e1rm = _estimate_1rm(s.get("actual_weight"), s.get("actual_reps"), uses_bodyweight)
        score = _set_score(s.get("actual_weight"), s.get("actual_reps"), uses_bodyweight)
        if e1rm is not None:
            best_e1rm = max(best_e1rm or 0, e1rm)
        best_score = max(best_score or 0, score)

    row_updates = {
        "current_target_weight": next_weight,
        "current_target_reps": next_reps,
        "current_uses_bodyweight": next_bw,
        "qualifying_streak": streak,
        "last_completed_at": now(),
        "last_workout_session_exercise": session_exercise_row,
        "updated_at": now(),
    }

    if best_e1rm is not None:
        row_updates["strongest_estimated_1rm"] = max(best_e1rm, state["strongest_estimated_1rm"] or 0)
    if best_score is not None:
        row_updates["strongest_set_score"] = max(best_score, state["strongest_set_score"] or 0)

    state.update(**row_updates)
    return {"qualified": qualifies, "new_streak": streak}


def estimate_1rm(weight, reps, uses_bodyweight):
    return _estimate_1rm(weight, reps, uses_bodyweight)


def compute_set_score(weight, reps, uses_bodyweight):
    return _set_score(weight, reps, uses_bodyweight)
