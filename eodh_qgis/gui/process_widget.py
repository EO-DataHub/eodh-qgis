import os
from typing import Callable, Literal, Optional

import pyeodh
import requests
from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt import QtWidgets, uic

from eodh_qgis.gui.jobs_widget import JobsWidget
from eodh_qgis.gui.workflows_widget import WorkflowsWidget
from eodh_qgis.settings import Settings

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/process.ui")
)


class ProcessWidget(QtWidgets.QWidget, FORM_CLASS):
    """Widget containing workflow and job management functionality.

    Based on v1 main_dialog.py patterns.
    """

    def __init__(self, creds: dict[str, str], parent=None):
        """Constructor."""
        super(ProcessWidget, self).__init__(parent)
        self.setupUi(self)

        self.creds = creds
        self.ades_svc = None
        self.selected_button: Optional[QtWidgets.QPushButton] = None

        # Type hints for UI elements (from .ui file)
        self.workflows_button: QtWidgets.QPushButton
        self.jobs_button: QtWidgets.QPushButton
        self.content_widget: QtWidgets.QStackedWidget

        # Button-widget mapping (like v1 main_dialog)
        self.button_widget_map = {
            "workflows": {
                "button": self.workflows_button,
                "widget": None,
            },
            "jobs": {
                "button": self.jobs_button,
                "widget": None,
            },
        }

        # Connect button signals
        self.workflows_button.clicked.connect(
            lambda: self.handle_menu_button_clicked("workflows")
        )
        self.jobs_button.clicked.connect(
            lambda: self.handle_menu_button_clicked("jobs")
        )

        # Initialize ADES and widgets
        self.get_ades()
        if self.ades_svc is not None:
            self.setup_widgets()

    def get_ades(self):
        """Initialize the ADES service."""
        username = self.creds["username"]
        token = self.creds["token"]
        env = Settings().data["env"]

        url = "https://eodatahub.org.uk"
        if env == "production":
            url = "https://eodatahub.org.uk"
        elif env == "staging":
            url = "https://staging.eodatahub.org.uk"
        elif env == "test":
            url = "https://test.eodatahub.org.uk"

        QgsMessageLog.logMessage(
            f"Initializing ADES: env={env}, url={url}, username={username}",
            "EODH",
            Qgis.Info,
        )

        try:
            self.ades_svc = pyeodh.Client(
                base_url=url, username=username, token=token
            ).get_ades()
            QgsMessageLog.logMessage(
                "ADES service initialized successfully", "EODH", Qgis.Info
            )
        except requests.HTTPError as e:
            QgsMessageLog.logMessage(f"ADES HTTPError: {e}", "EODH", Qgis.Critical)
            QtWidgets.QMessageBox.critical(
                self, "Error", "Error logging in to ADES, validate your credentials."
            )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"ADES unexpected error: {e}", "EODH", Qgis.Critical
            )

    def setup_widgets(self):
        """Create workflow and job widgets after ADES is initialized."""
        assert self.ades_svc is not None
        self.button_widget_map["workflows"]["widget"] = WorkflowsWidget(
            ades_svc=self.ades_svc, parent=self.content_widget
        )
        self.content_widget.addWidget(self.button_widget_map["workflows"]["widget"])

        self.button_widget_map["jobs"]["widget"] = JobsWidget(
            ades_svc=self.ades_svc, parent=self.content_widget
        )
        self.content_widget.addWidget(self.button_widget_map["jobs"]["widget"])

        # Show workflows by default
        self.handle_menu_button_clicked("workflows")

    def handle_menu_button_clicked(
        self,
        action: Literal["workflows", "jobs"],
        invoke_fn: Optional[Callable] = None,
    ):
        """Handle menu button click - switch between workflows and jobs views."""
        button = self.button_widget_map[action]["button"]
        widget = self.button_widget_map[action]["widget"]
        if button is self.selected_button:
            return

        if not widget:
            # Widget not initialized yet
            return

        self.content_widget.setCurrentWidget(widget)
        self.style_menu_button(button)

        if invoke_fn is not None:
            invoke_fn()

    def style_menu_button(self, button: QtWidgets.QPushButton):
        """Style the selected menu button."""
        if self.selected_button:
            self.selected_button.setProperty("selected", False)
            self.selected_button.style().unpolish(self.selected_button)
            self.selected_button.style().polish(self.selected_button)

        self.selected_button = button
        assert self.selected_button is not None
        self.selected_button.setProperty("selected", True)
        self.selected_button.style().unpolish(self.selected_button)
        self.selected_button.style().polish(self.selected_button)
