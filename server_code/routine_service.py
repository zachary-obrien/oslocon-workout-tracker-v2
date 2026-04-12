from exercise_service import get_canonical_exercise_by_name
from table_helpers import get_active_days, get_day_by_code, now
from anvil.tables import app_tables


PRESET_ROUTINE = {
    "A": [
        {"legacy_name": "Dumbell Row (2-Arm)", "sets": 5, "reps": 12, "weight": 40, "uses_bodyweight": False},
        {"legacy_name": "Dumbbell Press (Medium Incline)", "sets": 5, "reps": 12, "weight": 40, "uses_bodyweight": False},
        {"legacy_name": "Dumbell Curl (2 Arm)", "sets": 5, "reps": 12, "weight": 20, "uses_bodyweight": False},
        {"legacy_name": "Dumbbell Skull Crusher", "sets": 5, "reps": 12, "weight": 15, "uses_bodyweight": False},
        {"legacy_name": "Dumbell Split Squat", "sets": 2, "reps": 12, "weight": 20, "uses_bodyweight": False},
        {"legacy_name": "Bodyweight Squat", "sets": 2, "reps": 12, "weight": None, "uses_bodyweight": True},
    ],
    "B": [
        {"legacy_name": "Dumbell Row (2-Arm)", "sets": 5, "reps": 12, "weight": 40, "uses_bodyweight": False},
        {"legacy_name": "Dumbbell Press (Medium Incline)", "sets": 5, "reps": 12, "weight": 40, "uses_bodyweight": False},
        {"legacy_name": "Dumbell Curl (2 Arm)", "sets": 5, "reps": 12, "weight": 20, "uses_bodyweight": False},
        {"legacy_name": "Dumbbell Lateral Raise", "sets": 5, "reps": 12, "weight": 10, "uses_bodyweight": False},
        {"legacy_name": "Dumbell Stiff Legged Deadlift", "sets": 2, "reps": 12, "weight": 40, "uses_bodyweight": False},
        {"legacy_name": "Standing Calf Raise", "sets": 2, "reps": 15, "weight": None, "uses_bodyweight": True},
    ],
}


def ensure_preset_routine(user):
    existing = get_active_days(user)
    if existing:
        return existing

    created_days = []
    for day_index, (day_code, slot_defs) in enumerate(PRESET_ROUTINE.items(), start=1):
        day_row = app_tables.workout_days.add_row(
            user=user,
            day_code=day_code,
            display_order=day_index,
            is_active=True,
            created_at=now(),
            updated_at=now(),
            archived_at=None,
        )
        created_days.append(day_row)

        for idx, slot_def in enumerate(slot_defs, start=1):
            exercise = get_canonical_exercise_by_name(slot_def["legacy_name"])
            app_tables.workout_slots.add_row(
                user=user,
                workout_day=day_row,
                slot_number=idx,
                display_order=idx,
                exercise=exercise,
                is_active=True,
                base_target_weight=slot_def["weight"],
                base_target_reps=slot_def["reps"],
                default_sets=slot_def["sets"],
                uses_bodyweight=slot_def["uses_bodyweight"],
                notes="",
                created_at=now(),
                updated_at=now(),
                archived_at=None,
            )

    user["onboarding_complete"] = True
    return created_days


def add_empty_slot(user, workout_day):
    slots = [r for r in app_tables.workout_slots.search(user=user, workout_day=workout_day, is_active=True)]
    next_slot = max([s["slot_number"] or 0 for s in slots], default=0) + 1
    next_display = max([s["display_order"] or 0 for s in slots], default=0) + 1
    return app_tables.workout_slots.add_row(
        user=user,
        workout_day=workout_day,
        slot_number=next_slot,
        display_order=next_display,
        exercise=None,
        is_active=True,
        base_target_weight=None,
        base_target_reps=12,
        default_sets=5,
        uses_bodyweight=False,
        notes="",
        created_at=now(),
        updated_at=now(),
        archived_at=None,
    )


def add_workout_day(user):
    days = get_active_days(user)
    existing_codes = {d["day_code"] for d in days}
    code = "A"
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if c not in existing_codes:
            code = c
            break

    row = app_tables.workout_days.add_row(
        user=user,
        day_code=code,
        display_order=len(days) + 1,
        is_active=True,
        created_at=now(),
        updated_at=now(),
        archived_at=None,
    )
    return row


def remove_workout_day(user, day_code):
    day = get_day_by_code(user, day_code)
    if day is None:
        raise Exception("Workout day not found.")
    active_days = get_active_days(user)
    if len(active_days) <= 1:
        raise Exception("At least one workout day is required.")
    day.update(is_active=False, archived_at=now(), updated_at=now())
    for slot in app_tables.workout_slots.search(user=user, workout_day=day):
        slot.update(is_active=False, archived_at=now(), updated_at=now())
    remaining = get_active_days(user)
    for idx, row in enumerate(remaining, start=1):
        row["display_order"] = idx
    return remaining


def move_slot(user, workout_day, slot_number, direction):
    slots = [r for r in app_tables.workout_slots.search(user=user, workout_day=workout_day, is_active=True)]
    slots.sort(key=lambda r: (r["display_order"] or 9999, r["slot_number"] or 9999))
    index = next((i for i, s in enumerate(slots) if s["slot_number"] == slot_number), None)
    if index is None:
        raise Exception("Slot not found.")
    swap_index = index - 1 if direction == "up" else index + 1
    if swap_index < 0 or swap_index >= len(slots):
        return
    a = slots[index]
    b = slots[swap_index]
    a_order = a["display_order"]
    b_order = b["display_order"]
    a["display_order"] = b_order
    b["display_order"] = a_order


def remove_slot(user, workout_day, slot_number):
    slot = app_tables.workout_slots.get(user=user, workout_day=workout_day, slot_number=slot_number, is_active=True)
    if slot is None:
        raise Exception("Slot not found.")
    slot.update(is_active=False, archived_at=now(), updated_at=now())
    remaining = [r for r in app_tables.workout_slots.search(user=user, workout_day=workout_day, is_active=True)]
    remaining.sort(key=lambda r: (r["display_order"] or 9999, r["slot_number"] or 9999))
    for idx, row in enumerate(remaining, start=1):
        row["display_order"] = idx
