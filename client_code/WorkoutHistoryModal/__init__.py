from ._anvil_designer import WorkoutHistoryModalTemplate
from anvil import *
from datetime import datetime


class WorkoutHistoryModal(WorkoutHistoryModalTemplate):
  def __init__(self, history_items=None, exercise_name=None, current_day=None, current_exercise=None, **properties):
    self.init_components(**properties)
    self.history_items = history_items or []
    self.exercise_name = exercise_name
    self.current_day = current_day
    self.current_exercise = current_exercise
    self._build_ui()

  def _fmt(self, dt):
    if isinstance(dt, datetime):
      return dt.strftime("%m-%d-%Y %I:%M %p").lstrip("0").replace(" 0", " ")
    return str(dt or "")

  def _make_button(self, text, handler, role="button-secondary"):
    btn = Button(text=text, role=role)
    btn.spacing_above = "none"
    btn.spacing_below = "none"
    btn.set_event_handler("click", handler)
    return btn

  def _tile_text(self, item):
    tile_text = item.get("tile_text")
    if tile_text:
      return tile_text

    share = item.get("share_text") or ""
    for line in str(share).splitlines():
      line = line.strip()
      if line and any(ch in line for ch in ("🟩", "🟧", "🟥", "⬜", "⬛")):
        return line
    return ""

  def _history_html(self, item):
    top = item.get("day_code") or item.get("workout_day") or "—"
    timestamp = self._fmt(item.get("completed_at") or item.get("timestamp_ms"))
    tiles = self._tile_text(item)

    parts = [
      f"<div style='font-weight:800;color:#f3f6fb;line-height:1.12;margin:0 0 4px 0;'>Day {top}</div>",
      f"<div style='color:#97a5b7;line-height:1.15;margin:0 0 6px 0;'>{timestamp}</div>",
    ]
    if tiles:
      parts.append(f"<div style='line-height:1;margin:0;'>{tiles}</div>")

    secondary_note = item.get("secondary_label") or ""
    if secondary_note:
      parts.insert(0, f"<div style='color:#97a5b7;font-size:12px;line-height:1.1;margin:0 0 4px 0;'>{secondary_note}</div>")

    return "".join(parts)

  def _build_entry_card(self, item):
    card = ColumnPanel(role="card")
    card.spacing_above = "none"
    card.spacing_below = "small"
    try:
      card.background = "#1b2634"
      card.foreground = "#f3f6fb"
    except Exception:
      pass

    info = RichText(content=self._history_html(item), format="html")
    info.spacing_above = "none"
    info.spacing_below = "none"
    card.add_component(info, full_width_row=True)

    if not item.get("exercise_history", False):
      actions = FlowPanel(align="left")
      actions.spacing_above = "small"
      actions.spacing_below = "none"

      copy_btn = self._make_button(
        "Copy",
        lambda **e, row=item: self.raise_event("x-copy-history", item=row),
      )
      delete_btn = self._make_button(
        "Delete",
        lambda **e, row=item: self.raise_event("x-delete-history", item=row),
      )
      actions.add_component(copy_btn)
      actions.add_component(delete_btn)
      card.add_component(actions, full_width_row=True)

    return card

  def _build_filters(self):
    if self.exercise_name:
      return

    row = FlowPanel(align="left")
    row.spacing_above = "none"
    row.spacing_below = "small"
    row.add_component(self._make_button("Muscle group", lambda **e: self.raise_event("x-filter-muscle")))
    row.add_component(self._make_button("Current day", lambda **e: self.raise_event("x-filter-current-day")))
    row.add_component(self._make_button("All workouts", lambda **e: self.raise_event("x-filter-all")))
    self.root.add_component(row)

  def _build_ui(self):
    self.spacing_above = "none"
    self.spacing_below = "none"

    self.root = ColumnPanel(role="modal-card")
    self.root.spacing_above = "none"
    self.root.spacing_below = "none"
    self.add_component(self.root)

    head = FlowPanel(align="justify")
    head.spacing_above = "none"
    head.spacing_below = "small"
    title = "Workout history" if not self.exercise_name else self.exercise_name
    head.add_component(Label(text=title, role="exercise-title", spacing_above="none", spacing_below="none"))
    close = Button(text="✕", role="icon-button", spacing_above="none", spacing_below="none")
    close.set_event_handler("click", lambda **e: self.raise_event("x-close-modal"))
    head.add_component(close)
    self.root.add_component(head)

    subtitle = "Filter by workout, day, or muscle." if not self.exercise_name else "Previous workout / strongest day history"
    self.root.add_component(Label(text=subtitle, role="muted", spacing_above="none", spacing_below="small"))

    self._build_filters()

    if not self.history_items:
      self.root.add_component(Label(text="No completed workouts yet.", role="muted", spacing_above="small", spacing_below="none"))
      return

    for item in self.history_items:
      self.root.add_component(self._build_entry_card(item), full_width_row=True)
