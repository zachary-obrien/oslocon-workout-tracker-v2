from ._anvil_designer import WorkoutHistoryModalTemplate
from anvil import *
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
        self.root.add_component(Label(text="Most recent completed workouts" if not self.exercise_name else "Previous workout / strongest day history", role="muted"))
        if not self.history_items:
            self.root.add_component(Label(text="No completed workouts yet.", role="muted"))
            return
        for item in self.history_items:
            card = ColumnPanel(role="card")
            top = item.get("day_code") or item.get("workout_day") or "—"
            card.add_component(Label(text=f"Day {top}", bold=True))
            card.add_component(Label(text=self._fmt(item.get("completed_at") or item.get("timestamp_ms")), role="muted"))
            status = item.get("status") or item.get("completion_bucket")
            if status:
                card.add_component(Label(text=f"Status: {status}", role="muted"))
            share = item.get("share_text")
            if share:
                card.add_component(Label(text=share, role="muted"))
            self.root.add_component(card, full_width_row=True)
