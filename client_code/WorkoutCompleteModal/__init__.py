from ._anvil_designer import WorkoutCompleteModalTemplate
from anvil import *


class WorkoutCompleteModal(WorkoutCompleteModalTemplate):
    def __init__(self, summary=None, **properties):
        self.init_components(**properties)
        self.summary = summary or {}
        self._build_ui()

    def _tile_role(self, state):
        return {"green": "tile-green", "orange": "tile-orange", "red": "tile-red", "gray": "tile-gray"}.get(state, "tile-gray")

    def _build_ui(self):
        self.root = ColumnPanel(role="modal-card")
        self.add_component(self.root)
        head = FlowPanel(align="justify")
        head.add_component(Label(text="Workout Complete", role="exercise-title", spacing_above="none", spacing_below="none"))
        close = Button(text="✕", role="icon-button")
        close.set_event_handler("click", lambda **e: self.raise_event("x-close-modal"))
        head.add_component(close)
        self.root.add_component(head)
        self.root.add_component(Label(text=self.summary.get("headline", "Great work"), role="exercise-title", spacing_above="none", spacing_below="none"))
        self.root.add_component(Label(text=self.summary.get("message", ""), role="muted"))
        self.root.add_component(Label(text="Oslocon Workout!", bold=True))
        self.root.add_component(Label(text=self.summary.get("date", ""), role="muted"))
        tiles = FlowPanel()
        for state in self.summary.get("tile_states", []):
            lab = Label(text="  ")
            lab.width = 18
            lab.role = self._tile_role(state)
            tiles.add_component(lab)
        self.root.add_component(tiles)
        if self.summary.get("show_confetti"):
            self.root.add_component(Label(text="✨ 🎉 ✨", align="center", font_size=22))
        share = ColumnPanel(role="share-box")
        share.add_component(Label(text="Oslocon Workout!", bold=True))
        share.add_component(Label(text=self.summary.get("date", ""), role="muted"))
        share_tiles = FlowPanel()
        for state in self.summary.get("tile_states", []):
            lab = Label(text="  ")
            lab.width = 18
            lab.role = self._tile_role(state)
            share_tiles.add_component(lab)
        share.add_component(share_tiles)
        self.root.add_component(share)
        row = FlowPanel()
        copy_btn = Button(text="Copy", role="button-primary")
        close2 = Button(text="Close", role="button-secondary")
        copy_btn.set_event_handler("click", lambda **e: self.raise_event("x-copy", text=self.summary.get("share_text", "")))
        close2.set_event_handler("click", lambda **e: self.raise_event("x-close-modal"))
        row.add_component(copy_btn)
        row.add_component(close2)
        self.root.add_component(row)
