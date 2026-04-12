import anvil.server
import anvil.users

from table_helpers import ensure_user_defaults
from routine_service import ensure_preset_routine
from workout_service import build_workout_payload


LEGACY_PLACEHOLDER_NAMES = {"bootstrap user", "test user"}


def _require_logged_in_user():
    user = anvil.users.get_user()
    if user is None:
        try:
            user = anvil.users.login_with_google()
        except Exception as e:
            raise Exception(f"Google login is required. {e}")
    return user


def _display_name_for_user(user):
    raw = (user["display_name"] or "").strip()
    if raw and raw.lower() not in LEGACY_PLACEHOLDER_NAMES:
        return raw
    return ""


def _serialize_user(user):
    return {
        "email": user["email"] or "",
        "display_name": _display_name_for_user(user),
        "progress_every_n_qualifying_workouts": int(user["progress_every_n_qualifying_workouts"] or 3),
        "is_admin": bool(user["is_admin"]),
    }


@anvil.server.callable
def get_bootstrap_payload():
    user = _require_logged_in_user()
    ensure_user_defaults(user)

    display_name = _display_name_for_user(user)
    registration_required = not bool(display_name)
    workout = None if registration_required else build_workout_payload(user, None)

    return {
        "activeEmail": user["email"] or "",
        "activeEmailResolved": bool(user["email"]),
        "registrationRequired": registration_required,
        "userResolved": not registration_required,
        "user": _serialize_user(user),
        "workout": workout,
    }


@anvil.server.callable
def register_current_user(display_name):
    user = _require_logged_in_user()
    ensure_user_defaults(user)

    name = str(display_name or "").strip()
    if not name:
        raise Exception("Name is required.")

    user["display_name"] = name
    ensure_preset_routine(user)

    return {
        "activeEmail": user["email"] or "",
        "activeEmailResolved": bool(user["email"]),
        "registrationRequired": False,
        "userResolved": True,
        "user": _serialize_user(user),
        "workout": build_workout_payload(user, None),
    }
