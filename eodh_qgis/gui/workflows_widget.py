import os

from eodh_qgis.gui.wf_editor_widget import WorkflowEditorWidget
from eodh_qgis.gui.wf_executor_widget import WorkflowExecutorWidget
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
        self.edit_button: QtWidgets.QPushButton
        self.execute_button: QtWidgets.QPushButton

        self.new_button.clicked.connect(self.handle_new)
        self.edit_button.clicked.connect(self.handle_new)
        self.execute_button.clicked.connect(self.handle_execute)

    def handle_new(self):
        editor = WorkflowEditorWidget()
        self.parent().addWidget(editor)
        self.parent().setCurrentWidget(editor)

    def handle_execute(self):
        executor = WorkflowExecutorWidget()
        self.parent().addWidget(executor)
        self.parent().setCurrentWidget(executor)
