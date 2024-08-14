import os
from typing import Callable

import pyeodh
import requests
from qgis.PyQt import QtCore, QtGui, QtWidgets, uic

from eodh_qgis.gui.jobs_widget import JobsWidget
from eodh_qgis.gui.settings_widget import SettingsWidget
from eodh_qgis.gui.workflows_widget import WorkflowsWidget

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
        self.ades_svc = None
        self.get_ades()
        if self.ades_svc is None:
            self.reject()
            return
        self.content_widget: QtWidgets.QStackedWidget
        self.workflows_widget = WorkflowsWidget(ades_svc=self.ades_svc, parent=self)
        self.jobs_widget = JobsWidget(ades_svc=self.ades_svc)
        self.settings_widget = SettingsWidget()
        self.content_widget.addWidget(self.workflows_widget)
        self.content_widget.addWidget(self.jobs_widget)
        self.content_widget.addWidget(self.settings_widget)
        self.content_widget.setCurrentWidget(self.workflows_widget)

        self.workflows_button: QtWidgets.QPushButton
        self.jobs_button: QtWidgets.QPushButton
        self.settings_button: QtWidgets.QPushButton
        self.logo: QtWidgets.QLabel

        self.selected_button: QtWidgets.QPushButton = self.workflows_button

        self.workflows_button.clicked.connect(
            lambda: self.handle_menu_button_clicked(
                self.workflows_button,
                self.workflows_widget,
                self.workflows_widget.load_workflows,
            )
        )

        self.jobs_button.clicked.connect(
            lambda: self.handle_menu_button_clicked(
                self.jobs_button, self.jobs_widget, self.jobs_widget.load_jobs
            )
        )

        self.settings_button.clicked.connect(
            lambda: self.handle_menu_button_clicked(
                self.settings_button,
                self.settings_widget,
            )
        )

        self.logo.mousePressEvent = self.open_url
        self.logo.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def open_url(self, event):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://eodatahub.org.uk/"))

    def get_ades(self):
        username = os.getenv("ADES_USERNAME")
        token = os.getenv("ADES_TOKEN")
        s3_token = os.getenv("ADES_S3_TOKEN")

        if not username or not token or not s3_token:
            QtWidgets.QMessageBox.critical(
                self,
                "Missing credentials",
                "Configure environment variables ADES_USERNAME, ADES_TOKEN and "
                "ADES_S3_TOKEN.",
            )
            return

        try:
            self.ades_svc = pyeodh.Client(
                username=username, token=token, s3_token=s3_token
            ).get_ades()
        except requests.HTTPError:
            QtWidgets.QMessageBox.critical(
                self, "Error", "Error logging in, validate your credentials."
            )

    def handle_menu_button_clicked(
        self,
        button: QtWidgets.QPushButton,
        widget,
        invoke_fn: Callable | None = None,
    ):
        if button is self.selected_button:
            return

        self.content_widget.setCurrentWidget(widget)
        self.style_menu_button(button)

        if invoke_fn is not None:
            invoke_fn()

    def style_menu_button(self, button: QtWidgets.QPushButton):
        self.selected_button.setProperty("selected", False)
        self.selected_button.style().unpolish(self.selected_button)
        self.selected_button.style().polish(self.selected_button)

        self.selected_button = button
        self.selected_button.setProperty("selected", True)
        self.selected_button.style().unpolish(self.selected_button)
        self.selected_button.style().polish(self.selected_button)
