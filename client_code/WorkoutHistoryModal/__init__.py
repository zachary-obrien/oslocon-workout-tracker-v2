from ._anvil_designer import WorkoutHistoryModalTemplate
from anvil import *
import anvil.server
import anvil.js
from datetime import datetime


class WorkoutHistoryModal(WorkoutHistoryModalTemplate):
  def __init__(self, history_items=None, exercise_name=None, **properties):
    self.init_components(**properties)
    self.history_items = history_items or []
    self.exercise_name = exercise_name
    self._build_ui()

  def _fmt(self, dt):
    if isinstance(dt, datetime):
      return dt.strftime("%m-%d-%Y %I:%M %p").lstrip("0").replace(" 0", " ")
    return str(dt or "")

  def _copy_text(self, text):
    if not text:
      return
    try:
      anvil.js.window.navigator.clipboard.writeText(text)
      Notification("Copied.", timeout=1.5).show()
    except Exception:
      fallback = TextArea(text=text, height=140)
      fallback.enabled = True
      alert(content=fallback, title="Copy this text")

  def _delete_item(self, session_id):
    if not session_id:
      return
    if not confirm("Delete this workout history entry?", buttons=[("Delete", True), ("Cancel", False)]):
      return
    payload = anvil.server.call("delete_history_session", session_id)
    self.history_items = [x for x in self.history_items if x.get("session_id") != session_id]
    self.clear()
    self._build_ui()
    self.raise_event("x-history-deleted", payload=payload)

  def _build_ui(self):
    self.root = ColumnPanel(role="modal-card")
    self.add_component(self.root)

    head = FlowPanel(align="justify")
    title = "Workout history" if not self.exercise_name else self.exercise_name
    head.add_component(Label(text=title, role="exercise-title", spacing_above="none", spacing_below="none"))
    close = Button(text="✕", role="icon-button")
    close.set_event_handler("click", lambda **e: self.raise_event("x-close-modal"))
    head.add_component(close)
    self.root.add_component(head)

    subtitle = "Most recent completed workouts" if not self.exercise_name else "Previous workout / strongest day history"
    self.root.add_component(Label(text=subtitle, role="muted"))

    if not self.history_items:
      self.root.add_component(Label(text="No completed workouts yet.", role="muted"))
      return

    for item in self.history_items:
      card = ColumnPanel(role="card")
      top = item.get("day_code") or item.get("workout_day") or "—"
      card.add_component(Label(text=f"Day {top}", bold=True))

      date_text = item.get("completed_at_display") or self._fmt(item.get("completed_at") or item.get("timestamp_ms"))
      card.add_component(Label(text=date_text, role="muted"))

      status = item.get("status") or item.get("completion_bucket")
      if status:
        card.add_component(Label(text=f"Status: {status}", role="muted"))

      button_row = FlowPanel(gap="small")
      share = item.get("share_text") or ""
      copy_btn = Button(text="Copy", role="secondary-button")
      copy_btn.enabled = bool(share)
      copy_btn.set_event_handler("click", lambda text=share, **e: self._copy_text(text))
      button_row.add_component(copy_btn)

      if item.get("session_id"):
        delete_btn = Button(text="Delete", role="tertiary-button")
        delete_btn.set_event_handler("click", lambda session_id=item.get("session_id"), **e: self._delete_item(session_id))
        button_row.add_component(delete_btn)

      card.add_component(button_row)
      self.root.add_component(card, full_width_row=True)
