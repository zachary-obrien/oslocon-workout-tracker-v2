from ._anvil_designer import ChangeExerciseModalTemplate
from anvil import *
import anvil.server


class ChangeExerciseModal(ChangeExerciseModalTemplate):
    def __init__(self, current_name="", **properties):
        self.init_components(**properties)
        self.current_name = current_name or ""
        self._build_ui()
        self.search_box.text = self.current_name
        self.search()

    def _build_ui(self):
        self.root = ColumnPanel(role="modal-card")
        self.add_component(self.root)
        head = FlowPanel(align="justify")
        head.add_component(Label(text="Change Exercise", role="exercise-title", spacing_above="none", spacing_below="none"))
        close = Button(text="✕", role="icon-button")
        close.set_event_handler("click", lambda **e: self.raise_event("x-close-modal"))
        head.add_component(close)
        self.root.add_component(head)
        self.root.add_component(Label(text="Search the exercise database", role="muted"))
        search_row = FlowPanel()
        self.search_box = TextBox(placeholder="Search exercises...")
        self.search_btn = Button(text="Search", role="button-primary")
        search_row.add_component(self.search_box)
        search_row.add_component(self.search_btn)
        self.root.add_component(search_row)
        self.results = LinearPanel(spacing="small")
        self.root.add_component(self.results, full_width_row=True)
        self.search_btn.set_event_handler("click", self.search)
        self.search_box.set_event_handler("pressed_enter", self.search)

    def search(self, **event_args):
        rows = anvil.server.call("search_exercise_options", self.search_box.text or "")
        self.results.clear()
        for row in rows:
            card = ColumnPanel(role="card")
            btn = Button(text=row["name"], role="menu-item")
            btn.tag.exercise_id = row["exercise_id"]
            btn.set_event_handler("click", self.pick)
            card.add_component(btn)
            muscles = row.get("primary_muscles") or []
            meta = " • ".join([str(x).title() for x in muscles[:2]])
            if meta:
                card.add_component(Label(text=meta, role="muted"))
            self.results.add_component(card, full_width_row=True)

    def pick(self, **event_args):
        self.raise_event("x-exercise-picked", exercise_id=event_args["sender"].tag.exercise_id, sender=self)
