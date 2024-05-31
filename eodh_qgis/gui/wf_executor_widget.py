import os

from qgis.PyQt import QtWidgets, uic

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/wf_executor.ui")
)


class WorkflowExecutorWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(WorkflowExecutorWidget, self).__init__(parent)
        self.setupUi(self)
        self.cancel_button.clicked.connect(self.handle_cancel)

    def handle_cancel(self):
        self.parent().removeWidget(self)
        self.parent().setCurrentIndex(0)
