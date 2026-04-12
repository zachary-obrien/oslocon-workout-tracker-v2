from ._anvil_designer import ProgressionSettingsModalTemplate
from anvil import *


class ProgressionSettingsModal(ProgressionSettingsModalTemplate):
    def __init__(self, current_value=3, **properties):
        self.init_components(**properties)
        self.current_value = int(current_value or 3)
        self._build_ui()

    def _build_ui(self):
        self.root = ColumnPanel(role="modal-card")
        self.add_component(self.root)
        head = FlowPanel(align="justify")
        head.add_component(Label(text="Progression Settings", role="exercise-title", spacing_above="none", spacing_below="none"))
        close = Button(text="✕", role="icon-button")
        close.set_event_handler("click", lambda **e: self.raise_event("x-close-modal"))
        head.add_component(close)
        self.root.add_component(head)
        self.root.add_component(Label(text="Increase weight after this many qualifying workouts:", role="muted"))
        self.dropdown = DropDown(items=[(str(i), i) for i in range(1, 7)], selected_value=self.current_value, role="select")
        self.root.add_component(self.dropdown)
        save = Button(text="Save", role="button-primary")
        save.set_event_handler("click", lambda **e: self.raise_event("x-save-progress", value=self.dropdown.selected_value))
        self.root.add_component(save)
