from ._anvil_designer import AutoCompleteWorkoutModalTemplate
from anvil import *


class AutoCompleteWorkoutModal(AutoCompleteWorkoutModalTemplate):
    def __init__(self, has_skipped=False, **properties):
        self.init_components(**properties)
        self.has_skipped = has_skipped
        self._build_ui()

    def _build_ui(self):
        self.root = ColumnPanel(role="modal-card")
        self.add_component(self.root)
        head = FlowPanel(align="justify")
        head.add_component(Label(text="Workout complete?", role="exercise-title", spacing_above="none", spacing_below="none"))
        close = Button(text="✕", role="icon-button")
        close.set_event_handler("click", lambda **e: self.raise_event("x-close-modal"))
        head.add_component(close)
        self.root.add_component(head)
        txt = "All sets finished. Want to log the workout?" if not self.has_skipped else "All sets finished or skipped. Want to log the workout?"
        self.root.add_component(Label(text=txt, role="muted"))
        row = FlowPanel()
        keep = Button(text="Keep Editing", role="button-secondary")
        complete = Button(text="Complete Workout", role="button-primary")
        keep.set_event_handler("click", lambda **e: self.raise_event("x-close-modal"))
        complete.set_event_handler("click", lambda **e: self.raise_event("x-complete-now"))
        row.add_component(keep)
        row.add_component(complete)
        self.root.add_component(row)
