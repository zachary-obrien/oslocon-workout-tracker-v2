from ._anvil_designer import ExerciseCardTemplate
from anvil import *

from ..SetRow import SetRow


class ExerciseCard(ExerciseCardTemplate):
    def __init__(self, exercise_index=0, exercise_data=None, **properties):
        self.init_components(**properties)
        self.exercise_index = exercise_index
        self.exercise_data = dict(exercise_data or {})
        self.menu_open = False
        self._build_ui()
        self.render()

    def _build_ui(self):
        self.root = ColumnPanel(role="exercise-card")
        self.add_component(self.root)

        self.header = GridPanel(role="exercise-header")
        self.root.add_component(self.header, full_width_row=True, spacing_above="none", spacing_below="none")

        self.title_label = Label(text="", role="exercise-title", spacing_above="none", spacing_below="none")
        self.header.add_component(self.title_label, row="A", col_xs=0, width_xs=7)

        self.header_right = FlowPanel(align="right")
        self.pill_shell = FlowPanel(role="pill-shell")
        self.pill_text = Label(text="", role="pill-text", spacing_above="none", spacing_below="none")
        self.pill_shell.add_component(self.pill_text)
        self.menu_btn = Button(text="⋯", role="icon-button")
        self.edit_btn = Button(text="Edit", role="button-secondary", visible=False)
        self.header_right.add_component(self.pill_shell)
        self.header_right.add_component(self.menu_btn)
        self.header_right.add_component(self.edit_btn)
        self.header.add_component(self.header_right, row="A", col_xs=7, width_xs=5)

        self.menu_layer = ColumnPanel(role="exercise-menu-layer")
        self.menu_layer.visible = False
        self.root.add_component(self.menu_layer, full_width_row=True, spacing_above="none", spacing_below="none")
        self.menu_panel = LinearPanel(role="menu-popover", spacing="none")
        self.menu_view = Button(text="View history", role="menu-item")
        self.menu_change = Button(text="Change exercise", role="menu-item")
        self.menu_up = Button(text="Move up", role="menu-item")
        self.menu_down = Button(text="Move down", role="menu-item")
        self.menu_remove = Button(text="Remove exercise", role="menu-item-danger")
        self.menu_skip = Button(text="Skip exercise", role="menu-item-danger")
        for c in [self.menu_view, self.menu_change, self.menu_up, self.menu_down, self.menu_remove, self.menu_skip]:
            self.menu_panel.add_component(c, spacing_above="none", spacing_below="none")

        self.sets_panel = LinearPanel(spacing="none")
        self.root.add_component(self.sets_panel, full_width_row=True, spacing_above="none", spacing_below="none")

        self.summary_panel = ColumnPanel(role="exercise-summary")
        self.status_label = Label(text="", role="muted", spacing_above="none", spacing_below="none")
        self.summary_panel.add_component(self.status_label, spacing_above="none", spacing_below="none")
        self.root.add_component(self.summary_panel, full_width_row=True, spacing_above="none", spacing_below="none")

        self.menu_btn.set_event_handler("click", self.toggle_menu)
        self.edit_btn.set_event_handler("click", self.expand_from_parent)
        self.menu_view.set_event_handler("click", self.view_history)
        self.menu_change.set_event_handler("click", self.change_exercise)
        self.menu_up.set_event_handler("click", self.move_up)
        self.menu_down.set_event_handler("click", self.move_down)
        self.menu_remove.set_event_handler("click", self.remove_exercise)
        self.menu_skip.set_event_handler("click", self.skip_exercise)

    def _root_role(self):
        ex = self.exercise_data
        if ex.get("status") == "completed":
            return "exercise-card-done"
        if ex.get("status") == "skipped":
            return "exercise-card-skipped"
        if any(s.get("performed") for s in ex.get("sets", [])) and any(not s.get("performed") for s in ex.get("sets", [])):
            return "exercise-card-partial"
        return "exercise-card"

    def render(self):
        ex = self.exercise_data
        collapsed = (not ex.get("is_unassigned")) and ex.get("status") in ("completed", "skipped") and ex.get("collapsed") is not False
        self.root.role = self._root_role()
        self.header.role = "exercise-header-collapsed" if collapsed else "exercise-header"
        self.title_label.text = ex.get("exercise_label") or "Select exercise"
        self.pill_text.text = (ex.get("muscle_group") or ("Empty slot" if ex.get("is_unassigned") else "Unassigned")).title()

        self.menu_skip.visible = not ex.get("is_unassigned")
        self.menu_view.visible = not ex.get("is_unassigned")
        self.menu_up.enabled = bool(ex.get("can_move_up"))
        self.menu_down.enabled = bool(ex.get("can_move_down"))

        self.edit_btn.visible = collapsed
        self.menu_btn.visible = not collapsed
        if self.menu_open and not collapsed:
            self.menu_layer.clear()
            self.menu_layer.add_component(self.menu_panel, spacing_above="none", spacing_below="none")
            self.menu_layer.visible = True
        else:
            self.menu_layer.clear()
            self.menu_layer.visible = False

        self.sets_panel.visible = (not collapsed) and not ex.get("is_unassigned")
        self.summary_panel.visible = not ex.get("is_unassigned")

        self.sets_panel.clear()
        if ex.get("is_unassigned"):
            self.status_label.text = "This slot is empty. Choose an existing exercise."
            return

        if collapsed:
            self.status_label.text = self._collapsed_summary()
            return

        for idx, set_data in enumerate(ex.get("sets", [])):
            row = SetRow(exercise_index=self.exercise_index, set_index=idx, set_data=set_data, uses_bodyweight=bool(ex.get("uses_bodyweight")))
            row.set_event_handler("x-set-changed", self.set_changed)
            row.set_event_handler("x-add-set-below", self.add_set_below)
            row.set_event_handler("x-delete-set", self.delete_set)
            self.sets_panel.add_component(row, full_width_row=True, spacing_above="none", spacing_below="none")

        self.status_label.text = ""

    def _collapsed_summary(self):
        ex = self.exercise_data
        if ex.get("status") == "skipped":
            return "Skipped for this workout"
        sets = ex.get("sets", [])
        if not sets:
            return "Completed"
        checked = len([s for s in sets if s.get("performed")])
        avg_reps = round(sum(int(s.get("reps") or 0) for s in sets) / max(len(sets), 1))
        first_weight = sets[0].get("weight")
        weight_text = "BW" if ex.get("uses_bodyweight") else f"{first_weight} lb"
        return f"Completed · {checked}/{len(sets)} sets checked · {weight_text} · avg {avg_reps} reps"

    def toggle_menu(self, **event_args):
        self.menu_open = not self.menu_open
        self.render()

    def expand_from_parent(self, **event_args):
        self.exercise_data["collapsed"] = False
        if self.exercise_data.get("status") == "skipped":
            self.exercise_data["status"] = "active"
        self.raise_event("x-exercise-updated", exercise_index=self.exercise_index, exercise_data=self.exercise_data)

    def view_history(self, **event_args):
        self.menu_open = False
        self.raise_event("x-view-history", exercise_index=self.exercise_index, exercise_data=self.exercise_data)

    def change_exercise(self, **event_args):
        self.menu_open = False
        self.raise_event("x-change-exercise", exercise_index=self.exercise_index, exercise_data=self.exercise_data)

    def move_up(self, **event_args):
        self.menu_open = False
        self.raise_event("x-move-slot", exercise_index=self.exercise_index, direction="up", exercise_data=self.exercise_data)

    def move_down(self, **event_args):
        self.menu_open = False
        self.raise_event("x-move-slot", exercise_index=self.exercise_index, direction="down", exercise_data=self.exercise_data)

    def remove_exercise(self, **event_args):
        self.menu_open = False
        self.raise_event("x-remove-slot", exercise_index=self.exercise_index, exercise_data=self.exercise_data)

    def skip_exercise(self, **event_args):
        self.menu_open = False
        self.exercise_data["status"] = "skipped"
        self.exercise_data["collapsed"] = True
        self.raise_event("x-exercise-updated", exercise_index=self.exercise_index, exercise_data=self.exercise_data)

    def set_changed(self, exercise_index=None, set_index=None, set_data=None, **event_args):
        self.exercise_data["sets"][set_index] = dict(set_data)
        for idx in range(set_index + 1, len(self.exercise_data["sets"])):
            if self.exercise_data["sets"][idx].get("performed"):
                continue
            self.exercise_data["sets"][idx]["weight"] = set_data.get("weight")
            self.exercise_data["sets"][idx]["reps"] = set_data.get("reps")
        if all(s.get("performed") for s in self.exercise_data["sets"]):
            self.exercise_data["status"] = "completed"
            self.exercise_data["collapsed"] = True
        elif self.exercise_data.get("status") != "skipped":
            self.exercise_data["status"] = "active"
        self.raise_event("x-exercise-updated", exercise_index=self.exercise_index, exercise_data=self.exercise_data)

    def add_set_below(self, set_index=None, **event_args):
        src = dict(self.exercise_data["sets"][set_index])
        src["performed"] = False
        src["auto_completed"] = False
        self.exercise_data["sets"].insert(set_index + 1, src)
        self.raise_event("x-exercise-updated", exercise_index=self.exercise_index, exercise_data=self.exercise_data)

    def delete_set(self, set_index=None, **event_args):
        if len(self.exercise_data["sets"]) > 1:
            self.exercise_data["sets"].pop(set_index)
        else:
            self.exercise_data["sets"][0]["performed"] = False
            self.exercise_data["sets"][0]["auto_completed"] = False
        self.raise_event("x-exercise-updated", exercise_index=self.exercise_index, exercise_data=self.exercise_data)
