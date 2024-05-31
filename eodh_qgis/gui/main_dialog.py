import os

from eodh_qgis.gui.jobs_widget import JobsWidget
from eodh_qgis.gui.settings_widget import SettingsWidget
from qgis.PyQt import QtWidgets, uic

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
        self.content_widget: QtWidgets.QStackedWidget
        self.workflows_widget = WorkflowsWidget(parent=self)
        self.jobs_widget = JobsWidget()
        self.settings_widget = SettingsWidget()
        self.content_widget.addWidget(self.workflows_widget)
        self.content_widget.addWidget(self.jobs_widget)
        self.content_widget.addWidget(self.settings_widget)
        self.content_widget.setCurrentWidget(self.workflows_widget)

        self.workflows_button: QtWidgets.QPushButton
        self.jobs_button: QtWidgets.QPushButton
        self.settings_button: QtWidgets.QPushButton

        self.workflows_button.clicked.connect(
            lambda: self.content_widget.setCurrentWidget(self.workflows_widget)
        )

        self.jobs_button.clicked.connect(
            lambda: self.content_widget.setCurrentWidget(self.jobs_widget)
        )

        self.settings_button.clicked.connect(
            lambda: self.content_widget.setCurrentWidget(self.settings_widget)
        )
