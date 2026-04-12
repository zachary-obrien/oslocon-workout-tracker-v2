from ._anvil_designer import HistoryFormTemplate
from anvil import *


class HistoryForm(HistoryFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self.add_component(Label(text="History is opened from the top menu in the workout screen.", role="muted"))
