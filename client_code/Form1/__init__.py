from ._anvil_designer import Form1Template
from anvil import *
import anvil.server
import anvil.users

from ..CurrentWorkoutForm import CurrentWorkoutForm


class Form1(Form1Template):
  def __init__(self, **properties):
    self.init_components(**properties)
    self._mount()

  def _root_container(self):
    if hasattr(self, 'content_panel'):
      return self.content_panel
    if hasattr(self, 'column_panel_1'):
      return self.column_panel_1
    return self

  def _mount(self):
    root = self._root_container()
    try:
      root.clear()
    except Exception:
      pass

    if anvil.users.get_user() is None:
      anvil.users.login_with_google()

    bootstrap = anvil.server.call('get_bootstrap_payload')
    form = CurrentWorkoutForm(bootstrap_payload=bootstrap)

    if root is self:
      self.add_component(form)
    else:
      root.add_component(form, full_width_row=True, spacing_above='none', spacing_below='none')
