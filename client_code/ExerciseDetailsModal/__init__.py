from ._anvil_designer import ExerciseDetailsModalTemplate
from anvil import *
import anvil.server

BG = "#141c26"
SURFACE = "#10151d"
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

  def _clear_self(self):
    try:
      self.clear()
    except Exception:
      pass

  def _small_label(self, text, foreground=MUTED, bold=False):
    return Label(text=text, foreground=foreground, bold=bold, spacing_above="none", spacing_below="none")

  def _card(self):
    card = ColumnPanel(background=SURFACE, foreground=TEXT, spacing_above="small", spacing_below="none")
    try:
      card.border = f"1px solid {BORDER}"
    except Exception:
      pass
    return card

  def _section(self, title):
    self.add_component(Label(text=title, bold=True, foreground=TEXT, spacing_above="small", spacing_below="none"))

  def _build_ui(self):
    self._clear_self()
    self.background = BG
    self.foreground = TEXT
    try:
      self.border = None
    except Exception:
      pass

    head = FlowPanel(align="justify", spacing="small")
    head.spacing_above = "none"
    head.spacing_below = "none"
    title = self.detail.get("name") or "Exercise Details"
    head.add_component(Label(text=title, bold=True, font_size=18, foreground=TEXT, spacing_above="none", spacing_below="none"))
    close = Button(text="✕", role="button-secondary")
    close.set_event_handler("click", self._close)
    head.add_component(close)
    self.add_component(head)

    meta = []
    if self.detail.get("primary_muscles"):
      meta.append(", ".join(self.detail.get("primary_muscles") or []))
    if self.detail.get("equipment"):
      meta.append(self.detail.get("equipment"))
    if meta:
      self.add_component(self._small_label(" • ".join(meta)))

    tabs = FlowPanel(spacing="small")
    tabs.spacing_above = "small"
    tabs.spacing_below = "small"
    for key, label in (("detail", "Detail"), ("history", "History")):
      btn = Button(text=label, role="button-primary" if self.active_tab == key else "button-secondary")
      btn.set_event_handler("click", lambda key=key, **e: self._switch_tab(key))
      tabs.add_component(btn)
    self.add_component(tabs)

    if self.active_tab == "history":
      self._render_history_tab()
    else:
      self._render_detail_tab()

  def _switch_tab(self, tab_name):
    self.active_tab = tab_name
    self._build_ui()

  def _render_detail_tab(self):
    images = self.detail.get("images") or []
    self._section("Images")
    if images:
      current = images[self.image_index % len(images)]
      img = Image(source=current.get("media"), height=220)
      self.add_component(img, full_width_row=True)
      caption = current.get("label") or current.get("source_filename") or ""
      if caption:
        self.add_component(self._small_label(caption))
      if len(images) > 1:
        controls = FlowPanel(align="justify", spacing="small")
        prev_btn = Button(text="←", role="button-secondary")
        next_btn = Button(text="→", role="button-secondary")
        prev_btn.set_event_handler("click", lambda **e: self._step_image(-1))
        next_btn.set_event_handler("click", lambda **e: self._step_image(1))
        controls.add_component(prev_btn)
        controls.add_component(self._small_label(f"{self.image_index + 1} / {len(images)}"))
        controls.add_component(next_btn)
        self.add_component(controls)
    else:
      self.add_component(self._small_label("No exercise images yet."))

    self._section("Instructions")
    instructions = self.detail.get("instructions") or []
    if isinstance(instructions, str):
      instructions = [line.strip() for line in instructions.split("\n") if line.strip()] or [instructions]
    if instructions:
      for line in instructions:
        self.add_component(self._small_label(f"• {line}"))
    else:
      self.add_component(self._small_label("No instructions available."))

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
      self.add_component(self._small_label(f"{label}: {value}"))

  def _render_history_tab(self):
    filters = FlowPanel(spacing="small")
    filters.spacing_above = "small"
    filters.spacing_below = "small"
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
    self.add_component(filters)

    items = self._filtered_history_items()
    if not items:
      self.add_component(self._small_label("No history yet."))
      return

    for item in items:
      card = self._card()
      header = item.get("completed_at_display") or ""
      day = item.get("day_code") or ""
      title_bits = [x for x in [header, f"Day {day}" if day else ""] if x]
      if title_bits:
        card.add_component(Label(text=" • ".join(title_bits), bold=True, foreground=TEXT, spacing_above="none", spacing_below="none"))
      mode = MODE_LABELS.get(item.get("set_mode") or "standard", "Standard Sets")
      card.add_component(self._small_label(mode))
      for idx, set_info in enumerate(item.get("sets") or [], start=1):
        weight = set_info.get("weight") or "—"
        reps = set_info.get("reps") or "—"
        performed = "✓" if set_info.get("performed") else "○"
        card.add_component(self._small_label(f"{performed} Set {idx}: {weight} × {reps}"))
      if item.get("best_e1rm"):
        card.add_component(self._small_label(f"Estimated one rep max: {item['best_e1rm']}"))
      self.add_component(card, full_width_row=True)

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
