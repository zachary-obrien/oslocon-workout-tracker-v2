from ._anvil_designer import ExerciseDetailsModalTemplate
from anvil import *
import anvil.server


MODE_LABELS = {
  "standard": "Standard Sets",
  "myo_sets": "Myo Sets",
  "myo_rep_match": "Myo Rep Match Sets",
}


class ExerciseDetailsModal(ExerciseDetailsModalTemplate):
  def __init__(self, exercise_id=None, initial_tab="detail", current_day_code=None, **properties):
    self.init_components(**properties)
    self.exercise_id = exercise_id
    self.current_day_code = current_day_code
    self.active_tab = initial_tab if initial_tab in ("detail", "history") else "detail"
    self.active_history_filter = "all_history"
    self.image_index = 0
    self.detail = anvil.server.call("get_exercise_detail", exercise_id) if exercise_id else {}
    self.history_items = anvil.server.call("get_exercise_history", exercise_id) if exercise_id else []
    self._build_ui()

  def _close(self, **event_args):
    self.raise_event("x-close-alert")

  def _clear_root(self):
    try:
      self.clear()
    except Exception:
      pass

  def _build_ui(self):
    self._clear_root()
    self.root = ColumnPanel(role="modal-card")
    self.add_component(self.root)

    head = FlowPanel(align="justify")
    title = self.detail.get("name") or "Exercise Details"
    head.add_component(Label(text=title, role="exercise-title", spacing_above="none", spacing_below="none"))
    close = Button(text="✕", role="icon-button")
    close.set_event_handler("click", self._close)
    head.add_component(close)
    self.root.add_component(head)

    meta = []
    primary = self.detail.get("primary_muscles") or []
    if primary:
      meta.append(", ".join(primary))
    equipment = self.detail.get("equipment") or ""
    if equipment:
      meta.append(equipment)
    if meta:
      self.root.add_component(Label(text=" • ".join(meta), role="muted"))

    tab_row = FlowPanel(gap="small")
    self.detail_btn = Button(text="Detail", role="button-primary" if self.active_tab == "detail" else "button-secondary")
    self.history_btn = Button(text="History", role="button-primary" if self.active_tab == "history" else "button-secondary")
    self.detail_btn.set_event_handler("click", lambda **e: self._switch_tab("detail"))
    self.history_btn.set_event_handler("click", lambda **e: self._switch_tab("history"))
    tab_row.add_component(self.detail_btn)
    tab_row.add_component(self.history_btn)
    self.root.add_component(tab_row)

    self.content = ColumnPanel()
    self.root.add_component(self.content, full_width_row=True)
    self._render_active_tab()

  def _switch_tab(self, tab_name):
    self.active_tab = tab_name
    self._build_ui()

  def _render_active_tab(self):
    try:
      self.content.clear()
    except Exception:
      pass
    if self.active_tab == "history":
      self._render_history_tab()
    else:
      self._render_detail_tab()

  def _render_detail_tab(self):
    images = self.detail.get("images") or []
    if images:
      current = images[self.image_index % len(images)]
      img = Image(source=current.get("media"), height=260)
      self.content.add_component(img, full_width_row=True)
      if len(images) > 1:
        controls = FlowPanel(align="justify")
        prev_btn = Button(text="←", role="button-secondary")
        next_btn = Button(text="→", role="button-secondary")
        prev_btn.set_event_handler("click", lambda **e: self._step_image(-1))
        next_btn.set_event_handler("click", lambda **e: self._step_image(1))
        controls.add_component(prev_btn)
        controls.add_component(Label(text=f"{self.image_index + 1} / {len(images)}", role="muted"))
        controls.add_component(next_btn)
        self.content.add_component(controls)
      caption = current.get("label") or current.get("source_filename") or ""
      if caption:
        self.content.add_component(Label(text=caption, role="muted"))
    else:
      self.content.add_component(Label(text="No exercise images yet.", role="muted"))

    self._section_label("Instructions")
    instructions = self.detail.get("instructions") or []
    if isinstance(instructions, str):
      instructions = [instructions]
    if instructions:
      for line in instructions:
        self.content.add_component(Label(text=f"• {line}", role="muted"))
    else:
      self.content.add_component(Label(text="No instructions available.", role="muted"))

    self._section_label("Metadata")
    fields = [
      ("Group Size", self.detail.get("group_size") or "—"),
      ("Category", self.detail.get("category") or "—"),
      ("Equipment", self.detail.get("equipment") or "—"),
      ("Mechanic", self.detail.get("mechanic") or "—"),
      ("Force", self.detail.get("force") or "—"),
      ("Level", self.detail.get("level") or "—"),
      ("Primary Muscles", ", ".join(self.detail.get("primary_muscles") or []) or "—"),
      ("Secondary Muscles", ", ".join(self.detail.get("secondary_muscles") or []) or "—"),
    ]
    for label, value in fields:
      self.content.add_component(Label(text=f"{label}: {value}", role="muted"))

  def _render_history_tab(self):
    filters = FlowPanel(gap="small")
    options = [
      ("all_history", "All history"),
      ("strongest", "Strongest"),
      ("recent", "Recent"),
      ("current_day", "Current day"),
    ]
    for key, label in options:
      btn = Button(text=label, role="button-primary" if self.active_history_filter == key else "button-secondary")
      btn.enabled = not (key == "current_day" and not self.current_day_code)
      btn.set_event_handler("click", lambda key=key, **e: self._set_history_filter(key))
      filters.add_component(btn)
    self.content.add_component(filters)

    items = self._filtered_history_items()
    if not items:
      self.content.add_component(Label(text="No history yet.", role="muted"))
      return

    for item in items:
      card = ColumnPanel(role="card")
      header = item.get("completed_at_display") or ""
      day = item.get("day_code") or ""
      title_bits = [x for x in [header, f"Day {day}" if day else ""] if x]
      card.add_component(Label(text=" • ".join(title_bits), bold=True))
      mode = MODE_LABELS.get(item.get("set_mode") or "standard", "Standard Sets")
      status = item.get("status") or ""
      sub = f"{mode}"
      if status and status.lower() != "standard":
        sub += f" • {status}"
      card.add_component(Label(text=sub, role="muted"))
      for idx, set_info in enumerate(item.get("sets") or [], start=1):
        weight = set_info.get("weight") or "—"
        reps = set_info.get("reps") or "—"
        performed = "✓" if set_info.get("performed") else "○"
        card.add_component(Label(text=f"{performed} Set {idx}: {weight} × {reps}", role="muted"))
      metrics = []
      if item.get("best_e1rm"):
        metrics.append(f"Best e1RM {item['best_e1rm']}")
      if item.get("best_set_score"):
        metrics.append(f"Best score {item['best_set_score']}")
      if metrics:
        card.add_component(Label(text=" • ".join(metrics), role="muted"))
      self.content.add_component(card, full_width_row=True)

  def _set_history_filter(self, filter_key):
    self.active_history_filter = filter_key
    self._build_ui()

  def _filtered_history_items(self):
    items = list(self.history_items or [])
    if self.active_history_filter == "current_day" and self.current_day_code:
      items = [x for x in items if (x.get("day_code") or "") == self.current_day_code]
    elif self.active_history_filter == "recent":
      items = items[:8]
    elif self.active_history_filter == "strongest":
      items = sorted(items, key=lambda x: (x.get("best_e1rm") or 0, x.get("best_set_score") or 0, x.get("completed_at") or 0), reverse=True)[:8]
    return items

  def _step_image(self, direction):
    images = self.detail.get("images") or []
    if not images:
      return
    self.image_index = (self.image_index + direction) % len(images)
    self._build_ui()

  def _section_label(self, text):
    self.content.add_component(Label(text=text, bold=True, spacing_above="medium", spacing_below="small"))
