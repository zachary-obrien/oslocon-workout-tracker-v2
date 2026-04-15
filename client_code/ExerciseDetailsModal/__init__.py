from ._anvil_designer import ExerciseDetailsModalTemplate
from anvil import *
import anvil.server

APP_BG = "#0a1118"
TEXT = "#f3f6fb"
MUTED = "#97a5b7"
BORDER = "#283548"

MODE_LABELS = {
  "standard": "Standard Sets",
  "myo_sets": "Myo Sets",
  "myo_rep_match": "Myo Rep Match Sets",
}


class ExerciseDetailsModal(ExerciseDetailsModalTemplate):
  def __init__(self, exercise_id=None, initial_tab="detail", current_day_code=None, **properties):
    self.init_components(**properties)
    self.spacing_above = "none"
    self.spacing_below = "none"
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
    self.add_component(root)

    head = FlowPanel(align="justify", spacing="small")
    title = self.detail.get("name") or "Exercise Details"
    head.add_component(Label(text=title, bold=True, font_size=18, foreground=TEXT, spacing_above="none", spacing_below="none"))
    close = Button(text="✕", role="button-secondary")
    close.set_event_handler("click", self._close)
    head.add_component(close)
    root.add_component(head)

    meta = []
    if self.detail.get("primary_muscles"):
      meta.append(", ".join(self.detail.get("primary_muscles") or []))
    if self.detail.get("equipment"):
      meta.append(self.detail.get("equipment"))
    if meta:
      root.add_component(Label(text=" • ".join(meta), foreground=MUTED, spacing_above="none", spacing_below="small"))

    tabs = FlowPanel(spacing="small")
    for key, label in (("detail", "Detail"), ("history", "History")):
      btn = Button(text=label, role="button-primary" if self.active_tab == key else "button-secondary")
      btn.set_event_handler("click", lambda key=key, **e: self._switch_tab(key))
      tabs.add_component(btn)
    root.add_component(tabs)

    self.content = ColumnPanel()
    self.content.background = APP_BG
    root.add_component(self.content, full_width_row=True)
    if self.active_tab == "history":
      self._render_history_tab()
    else:
      self._render_detail_tab()

  def _switch_tab(self, tab_name):
    self.active_tab = tab_name
    self._build_ui()

  def _section(self, title):
    self.content.add_component(Label(text=title, bold=True, foreground=TEXT, spacing_above="small", spacing_below="none"))

  def _card(self):
    card = ColumnPanel()
    card.background = APP_BG
    card.foreground = TEXT
    try:
      card.border = f"1px solid {BORDER}"
    except Exception:
      pass
    return card

  def _render_detail_tab(self):
    images = self.detail.get("images") or []
    if images:
      self._section("Images")
      current = images[self.image_index % len(images)]
      self.content.add_component(Image(source=current.get("media"), height=220), full_width_row=True)
      if len(images) > 1:
        controls = FlowPanel(align="justify", spacing="small")
        prev_btn = Button(text="←", role="button-secondary")
        next_btn = Button(text="→", role="button-secondary")
        prev_btn.set_event_handler("click", lambda **e: self._step_image(-1))
        next_btn.set_event_handler("click", lambda **e: self._step_image(1))
        controls.add_component(prev_btn)
        controls.add_component(Label(text="", foreground=MUTED, spacing_above="none", spacing_below="none"))
        controls.add_component(next_btn)
        self.content.add_component(controls)
    else:
      self.content.add_component(Label(text="No exercise images yet.", foreground=MUTED, spacing_above="small", spacing_below="none"))

    self._section("Instructions")
    instructions = self.detail.get("instructions") or []
    if isinstance(instructions, str):
      instructions = [instructions]
    if instructions:
      for line in instructions:
        self.content.add_component(Label(text=f"• {line}", foreground=MUTED, spacing_above="none", spacing_below="none"))
    else:
      self.content.add_component(Label(text="No instructions available.", foreground=MUTED, spacing_above="none", spacing_below="none"))

    self._section("Metadata")
    fields = [
      ("Group size", self.detail.get("group_size") or "—"),
      ("Category", self.detail.get("category") or "—"),
      ("Equipment", self.detail.get("equipment") or "—"),
      ("Mechanic", self.detail.get("mechanic") or "—"),
      ("Force", self.detail.get("force") or "—"),
      ("Level", self.detail.get("level") or "—"),
      ("Primary muscles", ", ".join(self.detail.get("primary_muscles") or []) or "—"),
      ("Secondary muscles", ", ".join(self.detail.get("secondary_muscles") or []) or "—"),
    ]
    for label, value in fields:
      self.content.add_component(Label(text=f"{label}: {value}", foreground=MUTED, spacing_above="none", spacing_below="none"))

  def _render_history_tab(self):
    filters = FlowPanel(spacing="small")
    options = [("all_history", "All history"), ("strongest", "Strongest"), ("recent", "Recent"), ("current_day", "Current day")]
    for key, label in options:
      btn = Button(text=label, role="button-primary" if self.active_history_filter == key else "button-secondary")
      btn.enabled = not (key == "current_day" and not self.current_day_code)
      btn.set_event_handler("click", lambda key=key, **e: self._set_history_filter(key))
      filters.add_component(btn)
    self.content.add_component(filters)

    items = self._filtered_history_items()
    if not items:
      self.content.add_component(Label(text="No history yet.", foreground=MUTED, spacing_above="small", spacing_below="none"))
      return

    for item in items:
      card = self._card()
      header = item.get("completed_at_display") or ""
      day = item.get("day_code") or ""
      title_bits = [x for x in [header, f"Day {day}" if day else ""] if x]
      card.add_component(Label(text=" • ".join(title_bits), bold=True, foreground=TEXT, spacing_above="none", spacing_below="none"))
      card.add_component(Label(text=MODE_LABELS.get(item.get("set_mode") or "standard", "Standard Sets"), foreground=MUTED, spacing_above="none", spacing_below="none"))
      for idx, set_info in enumerate(item.get("sets") or [], start=1):
        weight = set_info.get("weight") or "—"
        reps = set_info.get("reps") or "—"
        performed = "✓" if set_info.get("performed") else "○"
        card.add_component(Label(text=f"{performed} Set {idx}: {weight} × {reps}", foreground=MUTED, spacing_above="none", spacing_below="none"))
      if item.get("best_e1rm"):
        card.add_component(Label(text=f"Estimated one rep max: {item['best_e1rm']}", foreground=MUTED, spacing_above="none", spacing_below="none"))
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
      items = sorted(items, key=lambda x: (x.get("best_e1rm") or 0, x.get("completed_at") or 0), reverse=True)[:8]
    return items

  def _step_image(self, direction):
    images = self.detail.get("images") or []
    if not images:
      return
    self.image_index = (self.image_index + direction) % len(images)
    self._build_ui()
