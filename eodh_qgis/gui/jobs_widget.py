import os

from eodh_qgis.gui.job_details_widget import JobDetailsWidget
from eodh_qgis.worker import Worker
import pyeodh.ades
from qgis.PyQt import QtWidgets, uic, QtCore

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "../ui/jobs.ui"))


class JobsWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, ades_svc: pyeodh.ades.Ades, parent=None):
        """Constructor."""
        super(JobsWidget, self).__init__(parent)
        self.setupUi(self)
        self.ades_svc = ades_svc
        self.jobs: list[pyeodh.ades.Job] = []
        self.row_selected = False
        self.threadpool = QtCore.QThreadPool()

        self.table: QtWidgets.QTableWidget
        self.details_button: QtWidgets.QPushButton
        self.refresh_button: QtWidgets.QPushButton
        self.auto_refresh: QtWidgets.QCheckBox

        self.table.cellClicked.connect(self.handle_table_click)
        self.details_button.clicked.connect(self.open_details)
        self.refresh_button.clicked.connect(self.load_jobs)

        self.load_jobs()

    def populate_table(self, jobs: list[pyeodh.ades.Job]):
        self.jobs = jobs
        headers = {
            "id": "ID",
            "process_id": "Process ID",
            "type": "type",
            "status": "Status",
            "progress": "Progress",
            "created": "Created",
            "started": "Started",
            "finished": "Finished",
            "updated": "Updated",
        }
        self.table.setRowCount(len(jobs))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(list(headers.values()))

        for row_index, job in enumerate(jobs):
            for col_index, key in enumerate(headers.keys()):
                self.table.setItem(
                    row_index,
                    col_index,
                    QtWidgets.QTableWidgetItem(str(getattr(job, key, ""))),
                )

        self.table.show()

    def handle_table_click(self, row, col):
        self.row_selected = True
        self.details_button.setEnabled(True)

    def open_details(self):
        selected_rows = self.table.selectionModel().selectedRows()
        job = self.jobs[selected_rows[0].row()]
        details = JobDetailsWidget(job=job, parent=self.parent())
        self.parent().addWidget(details)
        self.parent().setCurrentWidget(details)

    def load_jobs(self):
        self.lock_form(True)

        def load_data(*args, **kwargs):
            return self.ades_svc.get_jobs()

        worker = Worker(load_data)
        worker.signals.result.connect(self.populate_table)
        worker.signals.finished.connect(lambda: self.lock_form(False))
        self.threadpool.start(worker)

    def lock_form(self, locked: bool):
        self.refresh_button.setEnabled(not locked)
        self.details_button.setEnabled(not locked and self.row_selected)
        self.table.setEnabled(not locked)
        self.auto_refresh.setEnabled(not locked)
