from ._anvil_designer import WorkoutHistoryModalTemplate
from anvil import *
import anvil.server
import anvil.js


EMOJIS = {"green": "🟩", "orange": "🟧", "red": "🟥", "gray": "⬜"}


class WorkoutHistoryModal(WorkoutHistoryModalTemplate):
  def __init__(self, history_items=None, exercise_name=None, context_exercise_id=None, context_day_code=None, current_muscle_group=None, **properties):
    self.init_components(**properties)
    self.history_items = history_items or anvil.server.call("get_recent_history", 100)
    self.exercise_name = exercise_name
    self.context_exercise_id = str(context_exercise_id) if context_exercise_id not in (None, "") else None
    self.context_day_code = context_day_code
    self.current_muscle_group = current_muscle_group
    self.active_filter = "current_exercise" if self.context_exercise_id else "all_workouts"
    self.selected_muscle = current_muscle_group or self._first_muscle_option()
    self._build_ui()

  def _close(self, **event_args):
    self.raise_event("x-close-alert")

  def _first_muscle_option(self):
    options = self._muscle_options()
    return options[0] if options else None

  def _muscle_options(self):
    options = []
    seen = set()
    for item in self.history_items:
      for source in (item.get("primary_muscles") or [], item.get("secondary_muscles") or [], item.get("muscle_groups") or []):
        for muscle in source:
          key = str(muscle or "").strip()
          if key and key not in seen:
            seen.add(key)
            options.append(key)
    options.sort()
    return options

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
    with anvil.server.no_loading_indicator:
      anvil.server.call("delete_history_session", session_id)
    self.history_items = [x for x in self.history_items if str(x.get("session_id")) != str(session_id)]
    self._build_ui()

  def _set_filter(self, filter_key, **event_args):
    self.active_filter = filter_key
    self._build_ui()

  def _filtered_items(self):
    items = list(self.history_items or [])
    if self.active_filter == "current_exercise" and self.context_exercise_id:
      items = [x for x in items if self.context_exercise_id in {str(v) for v in (x.get("exercise_ids") or [])}]
    elif self.active_filter == "current_day" and self.context_day_code:
      items = [x for x in items if (x.get("day_code") or "") == self.context_day_code]
    elif self.active_filter == "muscle_group":
      selected = str(self.selected_muscle or "").strip()
      if selected:
        items = [x for x in items if selected in (x.get("primary_muscles") or []) or selected in (x.get("secondary_muscles") or []) or selected in (x.get("muscle_groups") or [])]
    return items

  def _tile_text(self, item):
    states = item.get("tile_states") or []
    return "".join(EMOJIS.get(state, "⬜") for state in states)

  def _build_ui(self):
    try:
      self.clear()
    except Exception:
      pass
    self.root = ColumnPanel(role="modal-card")
    self.add_component(self.root)

    head = FlowPanel(align="justify")
    title = self.exercise_name or "Workout history"
    head.add_component(Label(text=title, role="exercise-title", spacing_above="none", spacing_below="none"))
    close = Button(text="✕", role="icon-button")
    close.set_event_handler("click", self._close)
    head.add_component(close)
    self.root.add_component(head)

    subtitle = "Filters"
    self.root.add_component(Label(text=subtitle, role="muted"))

    controls = FlowPanel(gap="small")
    if self.context_exercise_id:
      btn = Button(text="Current exercise", role="button-primary" if self.active_filter == "current_exercise" else "button-secondary")
      btn.set_event_handler("click", lambda **e: self._set_filter("current_exercise"))
      controls.add_component(btn)

    muscle_options = self._muscle_options()
    if muscle_options:
      muscle_dd = DropDown(items=[(m, m) for m in muscle_options], selected_value=self.selected_muscle)
      muscle_dd.set_event_handler("change", self._muscle_changed)
      controls.add_component(muscle_dd)
      muscle_btn = Button(text="Muscle group", role="button-primary" if self.active_filter == "muscle_group" else "button-secondary")
      muscle_btn.set_event_handler("click", lambda **e: self._set_filter("muscle_group"))
      controls.add_component(muscle_btn)

    if self.context_day_code:
      btn = Button(text="Current day", role="button-primary" if self.active_filter == "current_day" else "button-secondary")
      btn.set_event_handler("click", lambda **e: self._set_filter("current_day"))
      controls.add_component(btn)

    all_btn = Button(text="All workouts", role="button-primary" if self.active_filter == "all_workouts" else "button-secondary")
    all_btn.set_event_handler("click", lambda **e: self._set_filter("all_workouts"))
    controls.add_component(all_btn)
    self.root.add_component(controls)

    items = self._filtered_items()
    if not items:
      self.root.add_component(Label(text="No history yet.", role="muted"))
      return

    for item in items:
      card = ColumnPanel(role="card")
      day = item.get("day_code") or "—"
      card.add_component(Label(text=f"Day {day}", bold=True))
      card.add_component(Label(text=item.get("completed_at_display") or "", role="muted"))
      tile_text = self._tile_text(item)
      if tile_text:
        card.add_component(Label(text=tile_text))
      names = item.get("exercise_names") or []
      if names:
        card.add_component(Label(text=", ".join(names[:4]) + ("…" if len(names) > 4 else ""), role="muted"))
      button_row = FlowPanel(gap="small")
      share = item.get("share_text") or ""
      copy_btn = Button(text="Copy", role="button-secondary")
      copy_btn.enabled = bool(share)
      copy_btn.set_event_handler("click", lambda text=share, **e: self._copy_text(text))
      button_row.add_component(copy_btn)
      if item.get("session_id"):
        delete_btn = Button(text="Delete", role="button-secondary")
        delete_btn.set_event_handler("click", lambda session_id=item.get("session_id"), **e: self._delete_item(session_id))
        button_row.add_component(delete_btn)
      card.add_component(button_row)
      self.root.add_component(card, full_width_row=True)

  def _muscle_changed(self, **event_args):
    dd = event_args.get("sender") if isinstance(event_args, dict) else None
    if dd is None:
      return
    self.selected_muscle = dd.selected_value
    self.active_filter = "muscle_group"
    self._build_ui()
