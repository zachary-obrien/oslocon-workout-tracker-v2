import re
from datetime import datetime, timezone

try:
  from zoneinfo import ZoneInfo
except ImportError:
  ZoneInfo = None


def normalize_for_match(text):
  text = str(text or "").strip().lower()
  text = re.sub(r"[^a-z0-9]+", " ", text)
  text = re.sub(r"\s+", " ", text).strip()
  return text


def smart_title_case(text):
  s = str(text or "").strip().lower()
  out = []
  capitalize_next = True
  for ch in s:
    if ch.isalpha():
      out.append(ch.upper() if capitalize_next else ch)
      capitalize_next = False
    else:
      out.append(ch)
      capitalize_next = True
  return "".join(out)


def format_weight(value, uses_bodyweight=False):
  if uses_bodyweight:
    return "BW"
  if value is None:
    return "—"
  try:
    num = float(value)
    if num.is_integer():
      return f"{int(num)} lb"
    return f"{num:g} lb"
  except Exception:
    return str(value)


def _coerce_to_timezone(dt, timezone_name="America/Chicago"):
  if not isinstance(dt, datetime):
    return None
  if ZoneInfo is None:
    return dt
  try:
    target_tz = ZoneInfo(timezone_name or "America/Chicago")
  except Exception:
    target_tz = ZoneInfo("America/Chicago")
  if dt.tzinfo is None:
    dt = dt.replace(tzinfo=timezone.utc)
  return dt.astimezone(target_tz)


def format_share_datetime(dt, timezone_name="America/Chicago"):
  dt = _coerce_to_timezone(dt, timezone_name)
  if not isinstance(dt, datetime):
    return ""
  mm = f"{dt.month:02d}"
  dd = f"{dt.day:02d}"
  yyyy = dt.year
  hour24 = dt.hour
  minute = f"{dt.minute:02d}"
  ampm = "PM" if hour24 >= 12 else "AM"
  hour12 = ((hour24 + 11) % 12) + 1
  return f"{mm}-{dd}-{yyyy} {hour12}:{minute} {ampm}"


def tile_to_emoji(tile_state):
  return {
    "green": "🟩",
    "orange": "🟧",
    "red": "🟥",
    "gray": "⬜",
  }.get(tile_state or "gray", "⬜")


import anvil.server
from datetime import datetime, timezone

try:
  from zoneinfo import ZoneInfo
except ImportError:
  ZoneInfo = None


@anvil.server.callable
def format_share_datetime_client(timezone_name="America/Chicago"):
  return format_share_datetime(datetime.now(timezone.utc), timezone_name)
