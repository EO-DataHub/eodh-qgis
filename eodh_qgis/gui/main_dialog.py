import os
from typing import Callable, Literal, Optional

import pyeodh
import requests
from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt import QtCore, QtGui, QtWidgets, uic

from eodh_qgis.gui.jobs_widget import JobsWidget
from eodh_qgis.gui.settings_widget import SettingsWidget
from eodh_qgis.gui.workflows_widget import WorkflowsWidget
from eodh_qgis.settings import Settings

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "../ui/main.ui"))


class MainDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(MainDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.content_widget: QtWidgets.QStackedWidget
        self.workflows_button: QtWidgets.QPushButton
        self.jobs_button: QtWidgets.QPushButton
        self.settings_button: QtWidgets.QPushButton
        self.logo: QtWidgets.QLabel
        self.selected_button: Optional[QtWidgets.QPushButton] = None
        self.ades_svc = None

        self.button_widget_map = {
            "settings": {
                "button": self.settings_button,
                "widget": SettingsWidget(parent=self),
            },
            "workflows": {
                "button": self.workflows_button,
                "widget": None,
            },
            "jobs": {
                "button": self.jobs_button,
                "widget": None,
            },
        }
        self.content_widget.addWidget(self.button_widget_map["settings"]["widget"])

        self.settings_button.clicked.connect(
            lambda: self.handle_menu_button_clicked("settings")
        )
        self.workflows_button.clicked.connect(
            lambda: self.handle_menu_button_clicked(
                "workflows",
                self.button_widget_map["workflows"]["widget"].load_workflows,
            )
        )
        self.jobs_button.clicked.connect(
            lambda: self.handle_menu_button_clicked(
                "jobs", self.button_widget_map["jobs"]["widget"].load_jobs
            )
        )

        self.logo.mousePressEvent = self.open_url
        self.logo.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setup_ui_after_token()

    def missing_creds(self):
        self.content_widget.setCurrentWidget(
            self.button_widget_map["settings"]["widget"]
        )
        self.selected_button = self.settings_button
        self.style_menu_button(self.selected_button)
        QtWidgets.QMessageBox.warning(
            self,
            "Missing credentials",
            "Configure authentication settings",
        )

    def setup_ui_after_token(self):
        self.creds = self.get_creds()
        if not self.creds:
            self.missing_creds()
            return

        self.get_ades()
        if self.ades_svc is None:
            self.missing_creds()
            return

        self.button_widget_map["workflows"]["widget"] = WorkflowsWidget(
            ades_svc=self.ades_svc, parent=self
        )
        self.content_widget.addWidget(self.button_widget_map["workflows"]["widget"])
        self.button_widget_map["jobs"]["widget"] = JobsWidget(ades_svc=self.ades_svc)
        self.content_widget.addWidget(self.button_widget_map["jobs"]["widget"])

        if self.selected_button is None:
            self.handle_menu_button_clicked("workflows")

    def open_url(self, event):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://eodatahub.org.uk/"))

    def get_ades(self):
        username = self.creds["username"]
        token = self.creds["token"]

        try:
            self.ades_svc = pyeodh.Client(username=username, token=token).get_ades()
        except requests.HTTPError:
            QtWidgets.QMessageBox.critical(
                self, "Error", "Error logging in, validate your credentials."
            )

    def handle_menu_button_clicked(
        self,
        action: Literal["settings", "workflows", "jobs"],
        invoke_fn: Optional[Callable] = None,
    ):
        button = self.button_widget_map[action]["button"]
        widget = self.button_widget_map[action]["widget"]
        if button is self.selected_button:
            return

        if not widget:
            self.setup_ui_after_token()
            widget = self.button_widget_map[action]["widget"]

        self.content_widget.setCurrentWidget(widget)
        self.style_menu_button(button)

        if invoke_fn is not None:
            invoke_fn()

    def style_menu_button(self, button: QtWidgets.QPushButton):
        if self.selected_button:
            self.selected_button.setProperty("selected", False)
            self.selected_button.style().unpolish(self.selected_button)
            self.selected_button.style().polish(self.selected_button)

        self.selected_button = button
        self.selected_button.setProperty("selected", True)
        self.selected_button.style().unpolish(self.selected_button)
        self.selected_button.style().polish(self.selected_button)

    def get_creds(self) -> dict[str, str]:
        settings = Settings()
        auth_config_id = settings.data["auth_config"]
        if not auth_config_id:
            return
        auth_mgr = QgsApplication.authManager()
        cfg = QgsAuthMethodConfig()
        auth_mgr.loadAuthenticationConfig(auth_config_id, cfg, True)
        creds = {
            "token": cfg.configMap().get("token"),
            "username": cfg.configMap().get("username"),
        }
        if not creds.get("token") or not creds.get("username"):
            return
        return creds
