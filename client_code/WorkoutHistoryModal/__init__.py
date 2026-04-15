from ._anvil_designer import WorkoutHistoryModalTemplate
from anvil import *
import anvil.server
import anvil.js

EMOJIS = {"green": "🟩", "orange": "🟧", "red": "🟥", "gray": "⬜"}
APP_BG = "#0a1118"
CARD_BG = "#1a2430"  # closer to set-row tone
BORDER = "#283548"
TEXT = "#f3f6fb"
MUTED = "#97a5b7"
BTN_ROLE = "button-secondary"
PRIMARY_ROLE = "button-primary"


class WorkoutHistoryModal(WorkoutHistoryModalTemplate):
  def __init__(self, history_items=None, exercise_name=None, context_exercise_id=None, context_day_code=None, current_muscle_group=None, **properties):
    self.init_components(**properties)
    self.spacing_above = "none"
    self.spacing_below = "none"
    self.history_items = history_items or anvil.server.call("get_recent_history", 100)
    self.exercise_name = exercise_name
    self.context_exercise_id = str(context_exercise_id) if context_exercise_id not in (None, "") else None
    self.context_day_code = context_day_code
    self.current_muscle_group = current_muscle_group
    self.active_filter = "current_exercise" if self.context_exercise_id else "all_workouts"
    self.selected_muscle = None
    self.muscle_history_items = []
    self._build_ui()

  def _close(self, **event_args):
    self.raise_event("x-close-alert")

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
    return sorted(options)

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
    if filter_key != "muscle_group":
      self.selected_muscle = None
      self.muscle_history_items = []
    self._build_ui()

  def _filtered_items(self):
    items = list(self.history_items or [])
    if self.active_filter == "current_exercise" and self.context_exercise_id:
      items = [x for x in items if self.context_exercise_id in {str(v) for v in (x.get("exercise_ids") or [])}]
    elif self.active_filter == "current_day" and self.context_day_code:
      items = [x for x in items if (x.get("day_code") or "") == self.context_day_code]
    return items

  def _tile_text(self, item):
    states = item.get("tile_states") or []
    return "".join(EMOJIS.get(state, "⬜") for state in states)

  def _make_card(self):
    card = ColumnPanel(role="card")
    card.background = CARD_BG
    card.foreground = TEXT
    try:
      card.border = f"1px solid {BORDER}"
    except Exception:
      pass
    card.spacing_above = "small"
    card.spacing_below = "none"
    return card

  def _tight_label(self, text, *, bold=False, fg=None, size=None):
    lbl = Label(text=text, bold=bold, foreground=fg or TEXT, spacing_above="none", spacing_below="none")
    if size is not None:
      lbl.font_size = size
    return lbl

  def _build_ui(self):
    try:
      self.clear()
    except Exception:
      pass
    self.background = APP_BG
    self.foreground = TEXT

    root = ColumnPanel()
    root.background = APP_BG
    root.foreground = TEXT
    root.spacing_above = "none"
    root.spacing_below = "none"
    self.add_component(root)

    head = FlowPanel(align="justify", spacing="small")
    title = self.exercise_name or "Workout history"
    head.add_component(self._tight_label(title, bold=True, size=18))
    close = Button(text="✕", role=BTN_ROLE)
    close.set_event_handler("click", self._close)
    head.add_component(close)
    root.add_component(head)
    root.add_component(self._tight_label("Filter by workout, day, or muscle.", fg=MUTED))

    controls = FlowPanel(spacing="small")
    if self.context_exercise_id:
      btn = Button(text="Current exercise", role=PRIMARY_ROLE if self.active_filter == "current_exercise" else BTN_ROLE)
      btn.set_event_handler("click", lambda **e: self._set_filter("current_exercise"))
      controls.add_component(btn)
    muscle_btn = Button(text="Muscle group", role=PRIMARY_ROLE if self.active_filter == "muscle_group" else BTN_ROLE)
    muscle_btn.set_event_handler("click", lambda **e: self._set_filter("muscle_group"))
    controls.add_component(muscle_btn)
    if self.context_day_code:
      btn = Button(text="Current day", role=PRIMARY_ROLE if self.active_filter == "current_day" else BTN_ROLE)
      btn.set_event_handler("click", lambda **e: self._set_filter("current_day"))
      controls.add_component(btn)
    all_btn = Button(text="All workouts", role=PRIMARY_ROLE if self.active_filter == "all_workouts" else BTN_ROLE)
    all_btn.set_event_handler("click", lambda **e: self._set_filter("all_workouts"))
    controls.add_component(all_btn)
    root.add_component(controls)

    if self.active_filter == "muscle_group":
      dd = DropDown(items=[("Select muscle…", None)] + [(m, m) for m in self._muscle_options()], selected_value=self.selected_muscle)
      dd.background = "#1b2634"
      dd.foreground = TEXT
      dd.set_event_handler("change", self._muscle_changed)
      root.add_component(dd)
      root.add_component(self._tight_label(f"Exercise history for {self.selected_muscle}" if self.selected_muscle else "Choose a muscle group to see exercise history.", fg=MUTED))

    items = self.muscle_history_items if self.active_filter == "muscle_group" and self.selected_muscle else self._filtered_items()
    if not items:
      root.add_component(self._tight_label("No history yet.", fg=MUTED))
      return

    for item in items:
      card = self._make_card()
      if self.active_filter == "muscle_group" and self.selected_muscle:
        self._render_muscle_history_card(card, item)
      else:
        self._render_workout_card(card, item)
      root.add_component(card, full_width_row=True)

  def _render_workout_card(self, card, item):
    day = item.get("day_code") or "—"
    card.add_component(self._tight_label(f"Day {day}", bold=True))

    completed = item.get("completed_at_display") or ""
    if completed:
      card.add_component(self._tight_label(completed, fg=MUTED))

    tile_text = self._tile_text(item)
    if tile_text:
      card.add_component(self._tight_label(tile_text, fg=TEXT))

    actions = FlowPanel(spacing="small")
    share = item.get("share_text") or ""
    copy_btn = Button(text="Copy", role=BTN_ROLE)
    copy_btn.enabled = bool(share)
    copy_btn.set_event_handler("click", lambda text=share, **e: self._copy_text(text))
    actions.add_component(copy_btn)
    if item.get("session_id"):
      delete_btn = Button(text="Delete", role=BTN_ROLE)
      delete_btn.set_event_handler("click", lambda session_id=item.get("session_id"), **e: self._delete_item(session_id))
      actions.add_component(delete_btn)
    card.add_component(actions)

  def _render_muscle_history_card(self, card, item):
    title = item.get("exercise_name") or "Exercise"
    if item.get("secondary_only"):
      title += " · Secondary muscle"
    card.add_component(self._tight_label(title, bold=True))

    sub_bits = []
    if item.get("day_code"):
      sub_bits.append(f"Day {item['day_code']}")
    if item.get("completed_at_display"):
      sub_bits.append(item.get("completed_at_display"))
    if sub_bits:
      card.add_component(self._tight_label(" • ".join(sub_bits), fg=MUTED))

    if item.get("set_mode_label"):
      card.add_component(self._tight_label(item.get("set_mode_label"), fg=MUTED))

    set_bits = []
    for idx, set_info in enumerate(item.get("sets") or [], start=1):
      if not set_info.get("performed"):
        continue
      weight = set_info.get("weight") or "—"
      reps = set_info.get("reps") or "—"
      set_bits.append(f"{idx}: {weight} × {reps}")
    if set_bits:
      card.add_component(self._tight_label(" · ".join(set_bits[:3]), fg=MUTED))

  def _muscle_changed(self, **event_args):
    sender = event_args.get("sender") if isinstance(event_args, dict) else None
    self.selected_muscle = sender.selected_value if sender else None
    self.muscle_history_items = anvil.server.call("get_muscle_history", self.selected_muscle) if self.selected_muscle else []
    self.active_filter = "muscle_group"
    self._build_ui()
