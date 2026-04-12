from ._anvil_designer import CurrentWorkoutFormTemplate
from anvil import *
import anvil.server

from ..ExerciseCard import ExerciseCard
from ..ChangeExerciseModal import ChangeExerciseModal
from ..WorkoutHistoryModal import WorkoutHistoryModal
from ..ProgressionSettingsModal import ProgressionSettingsModal
from ..UnfinishedWorkoutModal import UnfinishedWorkoutModal
from ..AutoCompleteWorkoutModal import AutoCompleteWorkoutModal
from ..WorkoutCompleteModal import WorkoutCompleteModal


class CurrentWorkoutForm(CurrentWorkoutFormTemplate):
    def __init__(self, bootstrap_payload=None, **properties):
        self.init_components(**properties)
        self.bootstrap_payload = bootstrap_payload or {}
        self.state = {
            "activeEmail": self.bootstrap_payload.get("activeEmail", ""),
            "activeEmailResolved": bool(self.bootstrap_payload.get("activeEmailResolved")),
            "registrationRequired": bool(self.bootstrap_payload.get("registrationRequired")),
            "userResolved": bool(self.bootstrap_payload.get("userResolved")),
            "user": self.bootstrap_payload.get("user") or {},
            "workout": self.bootstrap_payload.get("workout"),
        }
        self.exercise_cards = []
        self.modal_form = None
        self.auto_prompted = False
        self.suppress_auto_complete = False
        self._build_ui()
        self.render()

    def _build_ui(self):
        self.root = ColumnPanel(role="shell-wrap")
        self.add_component(self.root)

        self.subtitle = Label(text="", role="page-subtitle", spacing_above="none", spacing_below="none")
        self.root.add_component(self.subtitle, spacing_above="none", spacing_below="none")

        self.registration_card = ColumnPanel(role="card")
        self.root.add_component(self.registration_card, full_width_row=True, spacing_above="none", spacing_below="small")
        self.registration_help = Label(text="", role="muted")
        self.registration_name = TextBox(placeholder="Your name")
        self.registration_continue = Button(text="Continue", role="button-primary")
        self.registration_card.add_component(Label(text="Save your workouts", role="exercise-title", spacing_below="none"), spacing_above="none", spacing_below="none")
        self.registration_card.add_component(self.registration_help, spacing_above="none", spacing_below="small")
        self.registration_card.add_component(self.registration_name, spacing_above="none", spacing_below="small")
        self.registration_card.add_component(self.registration_continue, spacing_above="none", spacing_below="none")
        self.registration_continue.set_event_handler("click", self.register_continue_click)
        self.registration_name.set_event_handler("pressed_enter", self.register_continue_click)

        self.workout_area = ColumnPanel(role="workout-area")
        self.root.add_component(self.workout_area, full_width_row=True, spacing_above="none", spacing_below="none")

        self.hero = ColumnPanel(role="card hero-card")
        self.workout_area.add_component(self.hero, full_width_row=True, spacing_above="none", spacing_below="small")

        self.hero_top = GridPanel()
        self.hero.add_component(self.hero_top, full_width_row=True, spacing_above="none", spacing_below="none")

        self.hero_left = ColumnPanel()
        self.hero_title = Label(text="", role="exercise-title", spacing_above="none", spacing_below="none")
        self.day_helper = Label(text="", role="muted", spacing_above="none", spacing_below="none")
        self.hero_left.add_component(self.hero_title, spacing_above="none", spacing_below="none")
        self.hero_left.add_component(self.day_helper, spacing_above="none", spacing_below="none")
        self.hero_top.add_component(self.hero_left, row="A", col_xs=0, width_xs=8)

        self.hero_right = FlowPanel(align="right")
        self.day_selector = DropDown(include_placeholder=False, role="day-select")
        self.day_selector.width = 92
        self.top_menu_btn = Button(text="⋯", role="icon-button")
        self.hero_right.add_component(self.day_selector)
        self.hero_right.add_component(self.top_menu_btn)
        self.hero_top.add_component(self.hero_right, row="A", col_xs=8, width_xs=4)

        self.top_menu_layer = ColumnPanel(role="top-menu-layer")
        self.top_menu_panel = LinearPanel(role="menu-popover", spacing="none")
        self.top_menu_add_ex = Button(text="Add exercise", role="menu-item")
        self.top_menu_prog = Button(text="Progression settings", role="menu-item")
        self.top_menu_hist = Button(text="Workout history", role="menu-item")
        self.top_menu_add_day = Button(text="Add workout day", role="menu-item")
        self.top_menu_remove_day = Button(text="Remove current day", role="menu-item-danger")
        for c in [self.top_menu_add_ex, self.top_menu_prog, self.top_menu_hist, self.top_menu_add_day, self.top_menu_remove_day]:
            self.top_menu_panel.add_component(c, spacing_above="none", spacing_below="none")
        self.top_menu_layer.visible = False
        self.hero.add_component(self.top_menu_layer, full_width_row=True, spacing_above="none", spacing_below="none")

        self.hero_progress = FlowPanel()
        self.hero.add_component(self.hero_progress, spacing_above="none", spacing_below="none")

        self.exercise_list = LinearPanel(spacing="none")
        self.workout_area.add_component(self.exercise_list, full_width_row=True, spacing_above="none", spacing_below="none")

        self.footer_wrap = ColumnPanel(role="sticky-submit")
        self.root.add_component(self.footer_wrap, full_width_row=True, spacing_above="none", spacing_below="none")
        self.footer_card = ColumnPanel(role="card")
        self.footer_wrap.add_component(self.footer_card, full_width_row=True, spacing_above="none", spacing_below="none")
        self.complete_btn = Button(text="Workout Complete", role="button-primary")
        self.submit_msg = Label(text="", role="muted")
        self.submit_msg.visible = False
        self.credit = Label(text="Created by Agreadda", role="credit")
        self.footer_card.add_component(self.complete_btn, spacing_above="none", spacing_below="none")
        self.footer_card.add_component(self.submit_msg, spacing_above="none", spacing_below="none")
        self.footer_card.add_component(self.credit, spacing_above="none", spacing_below="none")

        self.modal_backdrop = ColumnPanel(role="modal-backdrop", visible=False)
        self.root.add_component(self.modal_backdrop, full_width_row=True, spacing_above="none", spacing_below="none")
        self.modal_host = ColumnPanel()
        self.modal_backdrop.add_component(self.modal_host, full_width_row=True, spacing_above="none", spacing_below="none")

        self.day_selector.set_event_handler("change", self.day_selector_change)
        self.top_menu_btn.set_event_handler("click", self.toggle_top_menu)
        self.top_menu_add_ex.set_event_handler("click", self.add_exercise_click)
        self.top_menu_prog.set_event_handler("click", self.open_progression_modal)
        self.top_menu_hist.set_event_handler("click", self.open_history_modal)
        self.top_menu_add_day.set_event_handler("click", self.add_day_click)
        self.top_menu_remove_day.set_event_handler("click", self.remove_day_click)
        self.complete_btn.set_event_handler("click", self.attempt_workout_complete)

    def _user_display_name(self):
        workout_user = (self.state.get("workout") or {}).get("resolvedUser") or {}
        user = self.state.get("user") or {}
        return workout_user.get("display_name") or user.get("display_name") or "User"

    def render(self):
        reg = bool(self.state.get("registrationRequired"))
        self.registration_card.visible = reg
        self.workout_area.visible = not reg
        self.footer_wrap.visible = not reg

        if reg:
            active = self.state.get("activeEmail") or ""
            self.registration_help.text = f"Saving as {active}. Enter your name to continue." if active else "Enter your name to continue."
            self.registration_name.text = ""
            self.subtitle.text = "Complete setup"
            return

        workout = self.state.get("workout") or {}
        display_name = self._user_display_name()
        email = self.state.get("activeEmail") or ""
        self.subtitle.text = f"Logged in as {display_name}{' • ' + email if email else ''}"
        self.hero_title.text = display_name
        self.day_helper.text = self._day_helper_text()
        self.top_menu_remove_day.visible = bool(workout.get("can_remove_current_day"))
        if self.top_menu_layer.visible:
            self._show_top_menu_panel()

        self.day_selector.items = [(f"Day {d['day_code']}", d["day_code"]) for d in workout.get("day_options", [])]
        self.day_selector.selected_value = workout.get("current_day")

        self._render_hero_progress()
        self._render_exercises()

    def _day_helper_text(self):
        workout = self.state.get("workout") or {}
        current_day = workout.get("current_day") or ""
        next_day = workout.get("next_scheduled_day") or current_day
        return f"Displayed Workout: Day {current_day}" if current_day == next_day else f"Displayed Workout: Day {current_day} • Next scheduled: Day {next_day}"

    def _render_hero_progress(self):
        self.hero_progress.clear()
        workout = self.state.get("workout") or {}
        exercises = [e for e in workout.get("exercises", []) if not e.get("is_unassigned")]
        total = len(exercises)
        completed = len([e for e in exercises if e.get("status") == "completed"])
        skipped = len([e for e in exercises if e.get("status") == "skipped"])
        remaining = total - completed - skipped
        rule = int((workout.get("progression_settings") or {}).get("progress_every_n_qualifying_workouts", 3))

        parts = [f"{completed} / {total} complete"]
        if skipped:
            parts.append(f"{skipped} skipped")
        if remaining:
            parts.append(f"{remaining} remaining")
        parts.append(f"Progress after {rule} qualifying workouts")

        for idx, text in enumerate(parts):
            if idx:
                self.hero_progress.add_component(Label(text="•", role="muted", spacing_above="none", spacing_below="none"), spacing_above="none", spacing_below="none")
            self.hero_progress.add_component(Label(text=text, role="muted", spacing_above="none", spacing_below="none"), spacing_above="none", spacing_below="none")

    def _render_exercises(self):
        self.exercise_list.clear()
        self.exercise_cards = []
        workout = self.state.get("workout") or {}
        exercises = workout.get("exercises", [])

        if not exercises:
            empty = ColumnPanel(role="card")
            empty.add_component(Label(text="No exercises on this day yet. Tap Add exercise to create a new slot.", role="muted"), spacing_above="none", spacing_below="none")
            self.exercise_list.add_component(empty, full_width_row=True, spacing_above="none", spacing_below="small")
            return

        for idx, ex in enumerate(exercises):
            card = ExerciseCard(exercise_index=idx, exercise_data=ex)
            card.set_event_handler("x-view-history", self.exercise_view_history)
            card.set_event_handler("x-change-exercise", self.exercise_change)
            card.set_event_handler("x-move-slot", self.exercise_move)
            card.set_event_handler("x-remove-slot", self.exercise_remove)
            card.set_event_handler("x-exercise-updated", self.exercise_updated)
            self.exercise_cards.append(card)
            self.exercise_list.add_component(card, full_width_row=True, spacing_above="none", spacing_below="none")

    def _refresh_workout(self, payload):
        self.state["workout"] = payload
        self.auto_prompted = False
        self.suppress_auto_complete = False
        self._close_top_menu()
        self.render()

    def day_selector_change(self, **event_args):
        payload = anvil.server.call("load_workout_day", self.day_selector.selected_value)
        self._refresh_workout(payload)

    def register_continue_click(self, **event_args):
        data = anvil.server.call("register_current_user", self.registration_name.text)
        self.state.update(data)
        self.render()

    def _show_top_menu_panel(self):
        self.top_menu_layer.clear()
        self.top_menu_layer.add_component(self.top_menu_panel, spacing_above="none", spacing_below="none")

    def toggle_top_menu(self, **event_args):
        self.top_menu_layer.visible = not self.top_menu_layer.visible
        if self.top_menu_layer.visible:
            self._show_top_menu_panel()
        else:
            self.top_menu_layer.clear()

    def _close_top_menu(self):
        self.top_menu_layer.visible = False
        self.top_menu_layer.clear()

    def add_exercise_click(self, **event_args):
        payload = anvil.server.call("add_exercise_slot", self.state["workout"]["current_day"])
        self._refresh_workout(payload)

    def add_day_click(self, **event_args):
        payload = anvil.server.call("add_workout_day")
        self._refresh_workout(payload)

    def remove_day_click(self, **event_args):
        payload = anvil.server.call("remove_workout_day", self.state["workout"]["current_day"])
        self._refresh_workout(payload)

    def open_progression_modal(self, **event_args):
        self._close_top_menu()
        current = int((self.state.get("workout") or {}).get("progression_settings", {}).get("progress_every_n_qualifying_workouts", 3))
        form = ProgressionSettingsModal(current)
        form.set_event_handler("x-close-modal", self.close_modal)
        form.set_event_handler("x-save-progress", self.save_progression_setting)
        self.open_modal(form)

    def save_progression_setting(self, value=None, **event_args):
        payload = anvil.server.call("update_progression_setting", value)
        self.close_modal()
        self._refresh_workout(payload)

    def open_history_modal(self, **event_args):
        self._close_top_menu()
        items = anvil.server.call("get_recent_history", 25)
        form = WorkoutHistoryModal(history_items=items)
        form.set_event_handler("x-close-modal", self.close_modal)
        self.open_modal(form)

    def exercise_view_history(self, exercise_data=None, **event_args):
        exercise_id = (exercise_data or {}).get("exercise_id")
        if not exercise_id:
            return
        items = anvil.server.call("get_exercise_history", exercise_id)
        form = WorkoutHistoryModal(history_items=items, exercise_name=(exercise_data or {}).get("exercise_label"))
        form.set_event_handler("x-close-modal", self.close_modal)
        self.open_modal(form)

    def exercise_change(self, exercise_data=None, **event_args):
        form = ChangeExerciseModal(current_name=(exercise_data or {}).get("exercise_label", ""))
        form.tag = {"slot_number": (exercise_data or {}).get("slot_number")}
        form.set_event_handler("x-close-modal", self.close_modal)
        form.set_event_handler("x-exercise-picked", self.exercise_picked)
        self.open_modal(form)

    def exercise_picked(self, exercise_id=None, sender=None, **event_args):
        slot_number = (sender.tag or {}).get("slot_number") if sender else None
        if slot_number is None:
            return
        payload = anvil.server.call("assign_slot_exercise", self.state["workout"]["current_day"], slot_number, exercise_id)
        self.close_modal()
        self._refresh_workout(payload)

    def exercise_move(self, exercise_data=None, direction=None, **event_args):
        payload = anvil.server.call("move_exercise_slot", self.state["workout"]["current_day"], exercise_data["slot_number"], direction)
        self._refresh_workout(payload)

    def exercise_remove(self, exercise_data=None, **event_args):
        payload = anvil.server.call("remove_exercise_slot", self.state["workout"]["current_day"], exercise_data["slot_number"])
        self._refresh_workout(payload)

    def exercise_updated(self, exercise_index=None, exercise_data=None, **event_args):
        if exercise_index is None:
            return
        self.state["workout"]["exercises"][exercise_index] = exercise_data
        self.render()
        if not self.suppress_auto_complete:
            self._maybe_open_auto_complete()

    def open_modal(self, form):
        self._close_top_menu()
        self.modal_host.clear()
        self.modal_form = form
        self.modal_backdrop.visible = True
        self.modal_host.add_component(form, full_width_row=True, spacing_above="none", spacing_below="none")

    def close_modal(self, **event_args):
        self.modal_host.clear()
        self.modal_backdrop.visible = False
        self.modal_form = None

    def _assigned_exercises(self):
        return [e for e in (self.state.get("workout") or {}).get("exercises", []) if not e.get("is_unassigned") and e.get("exercise_id")]

    def _all_done_or_skipped(self):
        exercises = self._assigned_exercises()
        return bool(exercises) and all(ex.get("status") == "skipped" or all(s.get("performed") for s in ex.get("sets", [])) for ex in exercises)

    def _first_unfinished_index(self):
        for idx, ex in enumerate((self.state.get("workout") or {}).get("exercises", [])):
            if ex.get("is_unassigned") or ex.get("status") == "skipped":
                continue
            if any(not s.get("performed") for s in ex.get("sets", [])):
                return idx
        return -1

    def _has_skips(self):
        return any(ex.get("status") == "skipped" for ex in self._assigned_exercises())

    def _maybe_open_auto_complete(self):
        if self.auto_prompted:
            return
        if self._all_done_or_skipped():
            self.auto_prompted = True
            form = AutoCompleteWorkoutModal(has_skipped=self._has_skips())
            form.set_event_handler("x-close-modal", self.close_modal)
            form.set_event_handler("x-complete-now", self.auto_complete_now)
            self.open_modal(form)

    def auto_complete_now(self, **event_args):
        self.close_modal()
        self.attempt_workout_complete()

    def attempt_workout_complete(self, **event_args):
        self.suppress_auto_complete = False
        if self._all_done_or_skipped():
            self.submit_workout()
            return
        form = UnfinishedWorkoutModal()
        form.set_event_handler("x-close-modal", self.close_modal)
        form.set_event_handler("x-go-back", self.unfinished_go_back)
        form.set_event_handler("x-complete-anyway", self.unfinished_complete_anyway)
        form.set_event_handler("x-finish-remaining", self.unfinished_finish_remaining)
        form.set_event_handler("x-complete-after-finish", self.unfinished_complete_after_finish)
        self.open_modal(form)

    def unfinished_go_back(self, **event_args):
        self.close_modal()
        idx = self._first_unfinished_index()
        if idx >= 0 and idx < len(self.exercise_cards):
            try:
                self.exercise_cards[idx].scroll_into_view()
            except Exception:
                pass

    def unfinished_complete_anyway(self, **event_args):
        self.close_modal()
        self.submit_workout()

    def unfinished_finish_remaining(self, **event_args):
        exercises = (self.state.get("workout") or {}).get("exercises", [])
        for ex in exercises:
            if ex.get("is_unassigned") or ex.get("status") == "skipped":
                continue
            for s in ex.get("sets", []):
                if not s.get("performed"):
                    s["performed"] = True
                    s["auto_completed"] = True
            ex["status"] = "completed"
            ex["collapsed"] = True
        self.auto_prompted = True
        self.suppress_auto_complete = True
        self.render()
        form = UnfinishedWorkoutModal(sets_autocompleted=True)
        form.set_event_handler("x-close-modal", self.close_modal)
        form.set_event_handler("x-go-back", self.unfinished_go_back)
        form.set_event_handler("x-complete-after-finish", self.unfinished_complete_after_finish)
        self.open_modal(form)

    def unfinished_complete_after_finish(self, **event_args):
        self.close_modal()
        self.submit_workout()

    def _collect_submit_payload(self):
        workout = self.state.get("workout") or {}
        payload = {"day_code": workout.get("current_day"), "exercises": []}
        for ex in workout.get("exercises", []):
            if ex.get("is_unassigned") or not ex.get("exercise_id"):
                continue
            payload["exercises"].append({
                "slot_number": ex.get("slot_number"),
                "exercise_id": ex.get("exercise_id"),
                "uses_bodyweight": ex.get("uses_bodyweight"),
                "recommended_weight": ex.get("recommended_weight"),
                "recommended_reps": ex.get("recommended_reps"),
                "status": ex.get("status"),
                "sets": ex.get("sets", []),
            })
        return payload

    def submit_workout(self):
        self.submit_msg.visible = True
        self.submit_msg.text = "Saving..."
        result = anvil.server.call("submit_workout", self._collect_submit_payload())
        self.submit_msg.text = ""
        self.submit_msg.visible = False
        self.state["workout"] = (result or {}).get("workout") or {}
        summary = (result or {}).get("completion_summary") or {}
        self.suppress_auto_complete = False
        self.auto_prompted = False
        modal = WorkoutCompleteModal(summary=summary)
        modal.set_event_handler("x-close-modal", self.close_modal)
        self.open_modal(modal)
        self.render()
