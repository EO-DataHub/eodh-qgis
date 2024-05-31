import os

from eodh_qgis.gui.wf_editor_widget import WorkflowEditorWidget
from qgis.PyQt import QtWidgets, uic

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/workflows.ui")
)


class WorkflowsWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(WorkflowsWidget, self).__init__(parent)
        self.setupUi(self)
        self.new_button: QtWidgets.QPushButton
        self.workflow_editor = WorkflowEditorWidget()
        self.new_button.clicked.connect(self.handle_new)

    def handle_new(self):
        self.parent().addWidget(self.workflow_editor)
        self.parent().setCurrentWidget(self.workflow_editor)
