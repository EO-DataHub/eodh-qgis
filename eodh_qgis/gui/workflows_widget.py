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
        self.table: QtWidgets.QTableWidget

        self.new_button.clicked.connect(self.handle_new)
        self.edit_button.clicked.connect(self.handle_new)
        self.execute_button.clicked.connect(self.handle_execute)
        self.populate_table_dummy()

    def handle_new(self):
        editor = WorkflowEditorWidget(parent=self.parent())
        self.parent().addWidget(editor)
        self.parent().setCurrentWidget(editor)

    def handle_execute(self):
        executor = WorkflowExecutorWidget(parent=self.parent())
        self.parent().addWidget(executor)
        self.parent().setCurrentWidget(executor)

    def populate_table_dummy(self):
        data = [
            ("id1", "title1", "description1"),
            ("id2", "title2", "description2"),
            ("id3", "title3", "description3"),
        ]
        self.table.setRowCount(len(data))
        self.table.setColumnCount(len(data[0]))
        self.table.setHorizontalHeaderLabels(["ID", "Title", "Description"])
        for row_index, row_data in enumerate(data):
            for col_index, col_data in enumerate(row_data):
                self.table.setItem(
                    row_index, col_index, QtWidgets.QTableWidgetItem(col_data)
                )

        self.table.show()
