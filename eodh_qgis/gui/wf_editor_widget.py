import os

from qgis.PyQt import QtWidgets, uic

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/wf_editor.ui")
)


class WorkflowEditorWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(WorkflowEditorWidget, self).__init__(parent)
        self.setupUi(self)

        self.content_widget: QtWidgets.QStackedWidget
        self.cwl_url_button: QtWidgets.QRadioButton
        self.cwl_yaml_button: QtWidgets.QRadioButton
        self.cancel_button: QtWidgets.QPushButton
        self.cwl_url_button.page_index = 0
        self.cwl_yaml_button.page_index = 1

        self.cwl_url_button.toggled.connect(self.handle_radio)
        self.cwl_yaml_button.toggled.connect(self.handle_radio)
        self.cancel_button.clicked.connect(self.handle_cancel)

    def handle_radio(self):
        btn = self.sender()
        if btn.isChecked():
            self.content_widget.setCurrentIndex(btn.page_index)

    def handle_cancel(self):
        self.parent().removeWidget(self)
        self.parent().setCurrentIndex(0)
