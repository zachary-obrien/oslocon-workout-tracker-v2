from ._anvil_designer import SetRowTemplate
from anvil import *


def _weight_options(uses_bodyweight):
    if uses_bodyweight:
        return [("BW", "BW")]
    vals = []
    x = 5.0
    while x <= 300:
        label = f"{int(x) if float(x).is_integer() else x:g}"
        vals.append((label, x))
        x += 2.5
    return vals


def _rep_options():
    return [(str(i), i) for i in range(3, 31)]


class SetRow(SetRowTemplate):
    def __init__(self, exercise_index=0, set_index=0, set_data=None, uses_bodyweight=False, **properties):
        self.init_components(**properties)
        self.exercise_index = exercise_index
        self.set_index = set_index
        self.set_data = dict(set_data or {})
        self.uses_bodyweight = uses_bodyweight
        self.menu_open = False
        self._build_ui()
        self.render()

    def _build_ui(self):
        self.root = ColumnPanel(role="set-row")
        self.add_component(self.root)

        self.grid = GridPanel()
        self.root.add_component(self.grid, full_width_row=True, spacing_above="none", spacing_below="none")

        self.menu_btn = Button(text="⋯", role="icon-button")
        self.grid.add_component(self.menu_btn, row="A", col_xs=0, width_xs=1)

        self.controls = FlowPanel(role="set-controls")
        self.weight_dd = DropDown(include_placeholder=False, role="select")
        self.weight_dd.width = 82
        self.weight_lbl = Label(text="lb", role="set-unit", spacing_above="none", spacing_below="none")
        self.reps_dd = DropDown(include_placeholder=False, role="select")
        self.reps_dd.width = 66
        self.reps_lbl = Label(text="reps", role="set-unit", spacing_above="none", spacing_below="none")
        self.controls.add_component(self.weight_dd)
        self.controls.add_component(self.weight_lbl)
        self.controls.add_component(self.reps_dd)
        self.controls.add_component(self.reps_lbl)
        self.grid.add_component(self.controls, row="A", col_xs=1, width_xs=10)

        self.check_btn = Button(text="", role="check-button")
        self.grid.add_component(self.check_btn, row="A", col_xs=11, width_xs=1)

        self.menu_layer = ColumnPanel(role="set-menu-layer")
        self.menu_layer.visible = False
        self.root.add_component(self.menu_layer, full_width_row=True, spacing_above="none", spacing_below="none")
        self.menu_panel = LinearPanel(role="menu-popover-left", spacing="none")
        self.add_btn = Button(text="Add set below", role="menu-item")
        self.delete_btn = Button(text="Delete set", role="menu-item-danger")
        self.menu_panel.add_component(self.add_btn, spacing_above="none", spacing_below="none")
        self.menu_panel.add_component(self.delete_btn, spacing_above="none", spacing_below="none")

        self.menu_btn.set_event_handler("click", self.toggle_menu)
        self.weight_dd.set_event_handler("change", self.value_changed)
        self.reps_dd.set_event_handler("change", self.value_changed)
        self.check_btn.set_event_handler("click", self.toggle_done)
        self.add_btn.set_event_handler("click", self.add_below)
        self.delete_btn.set_event_handler("click", self.delete_self)

    def _selected_weight_value(self):
        if self.uses_bodyweight:
            value = self.set_data.get("weight")
            return "BW" if value in (None, "", "BW") else value
        value = self.set_data.get("weight")
        options = [v for _, v in self.weight_dd.items]
        if value in options:
            return value
        try:
            numeric = float(value)
            if numeric in options:
                return numeric
        except Exception:
            pass
        return options[0] if options else None

    def render(self):
        self.root.role = "set-row-done" if self.set_data.get("performed") else "set-row"
        self.weight_dd.items = _weight_options(self.uses_bodyweight)
        self.reps_dd.items = _rep_options()
        self.weight_dd.selected_value = self._selected_weight_value()
        self.reps_dd.selected_value = self.set_data.get("reps") if self.set_data.get("reps") in [v for _, v in self.reps_dd.items] else 12
        self.weight_lbl.visible = not self.uses_bodyweight
        if self.menu_open:
            self.menu_layer.clear()
            self.menu_layer.add_component(self.menu_panel, spacing_above="none", spacing_below="none")
            self.menu_layer.visible = True
        else:
            self.menu_layer.clear()
            self.menu_layer.visible = False

        if self.set_data.get("performed"):
            self.check_btn.role = "check-button-checked"
            self.check_btn.text = "✓"
        else:
            self.check_btn.role = "check-button"
            self.check_btn.text = ""

    def toggle_menu(self, **event_args):
        self.menu_open = not self.menu_open
        self.render()

    def value_changed(self, **event_args):
        self.set_data["weight"] = self.weight_dd.selected_value
        self.set_data["reps"] = self.reps_dd.selected_value
        self.raise_event("x-set-changed", exercise_index=self.exercise_index, set_index=self.set_index, set_data=dict(self.set_data))

    def toggle_done(self, **event_args):
        self.set_data["performed"] = not self.set_data.get("performed")
        self.render()
        self.raise_event("x-set-changed", exercise_index=self.exercise_index, set_index=self.set_index, set_data=dict(self.set_data))

    def add_below(self, **event_args):
        self.menu_open = False
        self.render()
        self.raise_event("x-add-set-below", set_index=self.set_index)

    def delete_self(self, **event_args):
        self.menu_open = False
        self.render()
        self.raise_event("x-delete-set", set_index=self.set_index)
