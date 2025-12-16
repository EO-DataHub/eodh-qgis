from typing import Callable, Literal, Optional

import pyeodh
import requests
from qgis.PyQt import QtWidgets

from eodh_qgis.gui.v1.jobs_widget import JobsWidget
from eodh_qgis.gui.v1.workflows_widget import WorkflowsWidget
from eodh_qgis.settings import Settings


class ProcessWidget(QtWidgets.QWidget):
    """Widget containing workflow and job management functionality.

    Based on v1 main_dialog.py patterns.
    """

    def __init__(self, creds: dict[str, str], parent=None):
        """Constructor."""
        super(ProcessWidget, self).__init__(parent)
        self.creds = creds
        self.ades_svc = None
        self.selected_button: Optional[QtWidgets.QPushButton] = None

        # Main layout
        main_layout = QtWidgets.QVBoxLayout()

        # Toggle buttons for Workflows/Jobs
        button_layout = QtWidgets.QHBoxLayout()
        self.workflows_button = QtWidgets.QPushButton("Workflows")
        self.jobs_button = QtWidgets.QPushButton("Jobs")

        button_layout.addWidget(self.workflows_button)
        button_layout.addWidget(self.jobs_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Stacked widget to hold workflows and jobs widgets
        self.content_widget = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.content_widget)

        self.setLayout(main_layout)

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

        try:
            self.ades_svc = pyeodh.Client(
                base_url=url, username=username, token=token
            ).get_ades()
        except requests.HTTPError:
            QtWidgets.QMessageBox.critical(
                self, "Error", "Error logging in to ADES, validate your credentials."
            )

    def setup_widgets(self):
        """Create workflow and job widgets after ADES is initialized."""
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
        self.selected_button.setProperty("selected", True)
        self.selected_button.style().unpolish(self.selected_button)
        self.selected_button.style().polish(self.selected_button)
