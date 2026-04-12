from ._anvil_designer import Form1Template
from anvil import *
import anvil.server
import anvil.users

from ..CurrentWorkoutForm import CurrentWorkoutForm


class Form1(Form1Template):
    def __init__(self, **properties):
        self.init_components(**properties)
        self.bootstrap = None
        self._build_ui()
        self._ensure_logged_in()
        self._load_bootstrap()

    def _build_ui(self):
        root = self._root_container()
        root.clear()
        root.role = "app-root"

        self.shell = ColumnPanel(role="shell-wrap")
        root.add_component(self.shell, full_width_row=True)

        app_bar = FlowPanel(role="app-bar")
        self.shell.add_component(app_bar)
        try:
            logo = Image(source="_/theme/512x512OsloconWorkout.png", height=26)
            app_bar.add_component(logo)
        except Exception:
            pass
        app_bar.add_component(Label(text="Oslocon Workouts", role="app-title", spacing_above="none", spacing_below="none"))

        self.content_host = ColumnPanel()
        self.shell.add_component(self.content_host, full_width_row=True)

    def _root_container(self):
        if hasattr(self, "content_panel"):
            return self.content_panel
        if hasattr(self, "column_panel_1"):
            return self.column_panel_1
        c = ColumnPanel()
        self.add_component(c)
        return c

    def _ensure_logged_in(self):
        if anvil.users.get_user() is None:
            anvil.users.login_with_google()

    def _load_bootstrap(self):
        self.bootstrap = anvil.server.call("get_bootstrap_payload")
        self.content_host.clear()
        self.content_host.add_component(CurrentWorkoutForm(bootstrap_payload=self.bootstrap), full_width_row=True)
