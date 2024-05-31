import os

from eodh_qgis.gui.job_details_widget import JobDetailsWidget
from qgis.PyQt import QtWidgets, uic

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "../ui/jobs.ui"))


class JobsWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(JobsWidget, self).__init__(parent)
        self.setupUi(self)
        self.table: QtWidgets.QTableWidget
        self.details_button: QtWidgets.QPushButton
        self.populate_table_dummy()
        self.table.cellClicked.connect(self.handle_table_click)
        self.details_button.clicked.connect(self.open_details)

    def populate_table_dummy(self):
        data = [
            ("job1", "process1", "completed", "2024-05-31 10:36:56"),
            ("job2", "process2", "accepted", "2024-05-31 10:36:56"),
            ("job3", "process1", "completed", "2024-05-31 10:36:56"),
        ]
        self.table.setRowCount(len(data))
        self.table.setColumnCount(len(data[0]))
        self.table.setHorizontalHeaderLabels(["ID", "Process ID", "Status", "Created"])
        for row_index, row_data in enumerate(data):
            for col_index, col_data in enumerate(row_data):
                self.table.setItem(
                    row_index, col_index, QtWidgets.QTableWidgetItem(col_data)
                )

        self.table.show()

    def handle_table_click(self, row, col):
        print(row, col)
        self.details_button.setEnabled(True)

    def open_details(self):
        details = JobDetailsWidget(parent=self.parent())
        self.parent().addWidget(details)
        self.parent().setCurrentWidget(details)
