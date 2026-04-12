from ._anvil_designer import UnfinishedWorkoutModalTemplate
from anvil import *


class UnfinishedWorkoutModal(UnfinishedWorkoutModalTemplate):
    def __init__(self, sets_autocompleted=False, **properties):
        self.init_components(**properties)
        self.sets_autocompleted = sets_autocompleted
        self._build_ui()

    def _build_ui(self):
        self.root = ColumnPanel(role="modal-card")
        self.add_component(self.root)

        head = FlowPanel(align="justify")
        head.add_component(
            Label(
                text="Ready to complete" if self.sets_autocompleted else "Some sets are unfinished",
                role="exercise-title",
                spacing_above="none",
                spacing_below="none",
            )
        )
        close = Button(text="✕", role="icon-button")
        close.set_event_handler("click", lambda **e: self.raise_event("x-close-modal"))
        head.add_component(close)
        self.root.add_component(head, spacing_above="none", spacing_below="small")

        body_text = "Remaining sets auto-completed." if self.sets_autocompleted else "You can go back, complete anyway, or finish the remaining sets automatically."
        self.root.add_component(Label(text=body_text, role="muted"), spacing_above="none", spacing_below="small")

        split = GridPanel(role="modal-actions-split")
        go_back = Button(text="Go Back", role="button-modal-secondary")
        main = Button(text="Complete Workout" if self.sets_autocompleted else "Complete Anyway", role="button-modal-primary")
        go_back.width = "100%"
        main.width = "100%"
        go_back.set_event_handler("click", lambda **e: self.raise_event("x-go-back"))
        if self.sets_autocompleted:
            main.set_event_handler("click", lambda **e: self.raise_event("x-complete-after-finish"))
        else:
            main.set_event_handler("click", lambda **e: self.raise_event("x-complete-anyway"))
        split.add_component(go_back, row="A", col_xs=1, width_xs=4)
        split.add_component(main, row="A", col_xs=7, width_xs=4)
        self.root.add_component(split, full_width_row=True, spacing_above="none", spacing_below="none")

        if not self.sets_autocompleted:
            center = GridPanel(role="modal-center-row")
            finish = Button(text="Finish Remaining Sets", role="button-modal-subtle")
            finish.width = "100%"
            finish.set_event_handler("click", lambda **e: self.raise_event("x-finish-remaining"))
            center.add_component(finish, row="A", col_xs=3, width_xs=6)
            self.root.add_component(center, full_width_row=True, spacing_above="small", spacing_below="none")
