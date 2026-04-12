from ._anvil_designer import AccountFormTemplate
from anvil import *


class AccountForm(AccountFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self.add_component(Label(text="Account is not used in the 1:1 workflow.", role="muted"))
