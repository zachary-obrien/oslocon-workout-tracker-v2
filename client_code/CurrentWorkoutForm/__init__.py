from ._anvil_designer import CurrentWorkoutFormTemplate
from anvil import *
import anvil.server

from ..WorkoutHistoryModal import WorkoutHistoryModal
from ..ExerciseDetailsModal import ExerciseDetailsModal


class CurrentWorkoutForm(CurrentWorkoutFormTemplate):
  def __init__(self, bootstrap_payload=None, **properties):
    self.init_components(**properties)
    self.bootstrap_payload = bootstrap_payload or {}
    self.current_day = ((self.bootstrap_payload.get('workout') or {}).get('current_day'))
    self._js_ready = False
    self.set_event_handler('show', self.form_show)

  def form_show(self, **event_args):
    if self._js_ready:
      return
    self._js_ready = True
    self.call_js('bootstrapApp', self.bootstrap_payload)

  def _update_workout(self, payload):
    self.current_day = (payload or {}).get('current_day')
    if self._js_ready:
      self.call_js('updateWorkout', payload)
    return payload

  def py_register_current_user(self, name):
    data = anvil.server.call('register_current_user', name)
    merged = dict(self.bootstrap_payload)
    merged.update(data or {})
    self.bootstrap_payload = merged
    self.current_day = ((data or {}).get('workout') or data or {}).get('current_day')
    return data

  def py_load_workout_day(self, day_code):
    payload = anvil.server.call('load_workout_day', day_code)
    return self._update_workout(payload)

  def py_add_exercise_slot(self):
    payload = anvil.server.call('add_exercise_slot', self.current_day)
    return self._update_workout(payload)

  def py_add_workout_day(self):
    payload = anvil.server.call('add_workout_day')
    return self._update_workout(payload)

  def py_remove_current_workout_day(self):
    payload = anvil.server.call('remove_workout_day', self.current_day)
    return self._update_workout(payload)

  def py_move_exercise_slot(self, slot_number, direction):
    payload = anvil.server.call('move_exercise_slot', self.current_day, slot_number, direction)
    return self._update_workout(payload)

  def py_remove_exercise_slot(self, slot_number):
    payload = anvil.server.call('remove_exercise_slot', self.current_day, slot_number)
    return self._update_workout(payload)

  def py_assign_slot_exercise(self, slot_number, exercise_id):
    payload = anvil.server.call('assign_slot_exercise', self.current_day, slot_number, exercise_id)
    return self._update_workout(payload)

  def py_set_slot_mode(self, slot_number, mode):
    payload = anvil.server.call('set_exercise_set_mode', self.current_day, slot_number, mode)
    return self._update_workout(payload)

  def py_update_progression_setting(self, value):
    payload = anvil.server.call('update_progression_setting', value)
    return self._update_workout(payload)

  def py_get_recent_history(self):
    return anvil.server.call('get_recent_history', 100)

  def py_get_exercise_history(self, exercise_id):
    return anvil.server.call('get_exercise_history', exercise_id)

  def py_delete_history_session(self, session_id):
    with anvil.server.no_loading_indicator:
      return anvil.server.call('delete_history_session', session_id, self.current_day)

  def py_search_exercises(self, query):
    try:
      return anvil.server.call('search_exercises_ui', query)
    except Exception:
      return []

  def py_open_history_modal(self, context_exercise_id=None, current_muscle_group=None):
    modal = WorkoutHistoryModal(context_exercise_id=context_exercise_id, context_day_code=self.current_day, current_muscle_group=current_muscle_group)
    alert(content=modal, large=True, buttons=[])
    return True

  def py_open_exercise_details(self, exercise_id, initial_tab='detail'):
    modal = ExerciseDetailsModal(exercise_id=exercise_id, initial_tab=initial_tab, current_day_code=self.current_day)
    alert(content=modal, large=True, buttons=[])
    return True


  def py_save_workout_draft(self, payload):
    if not self.current_day:
      return None
    return anvil.server.call('save_workout_draft', self.current_day, payload)

  def py_clear_current_workout_changes(self):
    if not self.current_day:
      return None
    payload = anvil.server.call('clear_current_workout_changes', self.current_day)
    return self._update_workout(payload)

  def py_submit_workout(self, payload):
    result = anvil.server.call('submit_workout', payload)
    workout = (result or {}).get('workout') or {}
    self.current_day = workout.get('current_day')
    if self._js_ready:
      self.call_js('acceptSubmissionResult', result)
    return result
