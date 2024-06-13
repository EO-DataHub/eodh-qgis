import os

from eodh_qgis.gui.jobs_widget import JobsWidget
from eodh_qgis.gui.login_dialog import LoginDialog
from eodh_qgis.gui.settings_widget import SettingsWidget
from qgis.PyQt import QtWidgets, uic, QtGui, QtCore

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
        self.get_ades()
        if not self.ades_svc:
            self.close()
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

        self.workflows_button.clicked.connect(
            lambda: self.content_widget.setCurrentWidget(self.workflows_widget)
        )

        self.jobs_button.clicked.connect(
            lambda: self.content_widget.setCurrentWidget(self.jobs_widget)
        )

        self.settings_button.clicked.connect(
            lambda: self.content_widget.setCurrentWidget(self.settings_widget)
        )

        self.logo.mousePressEvent = self.open_url
        self.logo.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def open_url(self, event):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://eodatahub.org.uk/"))

    def get_ades(self):
        login_dialog = LoginDialog(parent=self)
        login_dialog.exec()
        self.ades_svc = login_dialog.ades_svc
