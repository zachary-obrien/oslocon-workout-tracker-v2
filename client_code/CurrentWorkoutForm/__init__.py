from ._anvil_designer import CurrentWorkoutFormTemplate
from anvil import *
import anvil.server


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
    # Custom HTML JS is only available after the form has been added to the DOM.
    self.call_js('bootstrapApp', self.bootstrap_payload)

    # ---------- JS bridge helpers ----------
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

  def py_update_progression_setting(self, value):
    payload = anvil.server.call('update_progression_setting', value)
    return self._update_workout(payload)

  def py_get_recent_history(self):
    return anvil.server.call('get_recent_history', 25)

  def py_get_exercise_history(self, exercise_id):
    return anvil.server.call('get_exercise_history', exercise_id)

  def py_search_exercises(self, query):
    try:
      return anvil.server.call('search_exercises_ui', query)
    except Exception:
      return []

  def py_submit_workout(self, payload):
    result = anvil.server.call('submit_workout', payload)
    workout = (result or {}).get('workout') or {}
    self.current_day = workout.get('current_day')
    if self._js_ready:
      self.call_js('acceptSubmissionResult', result)
    return result
