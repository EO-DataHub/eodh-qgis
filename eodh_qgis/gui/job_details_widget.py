import json
import os
import time

from eodh_qgis.worker import Worker
from qgis.PyQt import QtWidgets, uic, QtCore
import pyeodh.ades

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/job_detail.ui")
)


class JobDetailsWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, job: pyeodh.ades.Job, parent=None):
        """Constructor."""
        super(JobDetailsWidget, self).__init__(parent)
        self.job = job
        self.setupUi(self)
        self.threadpool = QtCore.QThreadPool()
        self.logs = {}
        self.read_logs()

        self.table: QtWidgets.QTableWidget
        self.message_log: QtWidgets.QTextBrowser
        self.close_button: QtWidgets.QPushButton
        self.stop_button: QtWidgets.QPushButton

        self.message_log.setText(self.logs.get(self.job.id))
        self.close_button.clicked.connect(self.handle_close)
        self.stop_button.clicked.connect(self.handle_stop)
        self.populate_table()

        if self.job.status in [
            pyeodh.ades.AdesJobStatus.RUNNING,
            pyeodh.ades.AdesJobStatus.ACCEPTED,
        ]:
            # self.stop_button.setEnabled(True) # ! ADES doesn't support job cancel yet
            self.trigger_polling()

    def handle_close(self):
        self.parent().removeWidget(self)
        self.parent().setCurrentIndex(1)

    def populate_table(self):
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
        self.table.setColumnCount(1)
        self.table.setRowCount(len(headers))
        self.table.setVerticalHeaderLabels(list(headers.values()))

        for row_index, key in enumerate(headers.keys()):
            self.table.setItem(
                row_index,
                0,
                QtWidgets.QTableWidgetItem(str(getattr(self.job, key, ""))),
            )

        self.table.show()

    def trigger_polling(self):
        worker = Worker(self.check_status)
        worker.signals.progress.connect(self.log_msg)
        worker.signals.finished.connect(self.save_logs)
        self.threadpool.start(worker)

    def log_msg(self, msg):
        self.message_log.append(msg)

    def check_status(self, progress_callback):
        timeout = 2
        progress_callback.emit(f"Checking job status (every {timeout}s)")
        old_status = ""
        old_message = ""

        while True:
            self.job.refresh()
            self.populate_table()

            if self.job.status != old_status:
                progress_callback.emit(f"\nStatus: {self.job.status}")
                old_status = self.job.status

            if self.job.message != old_message:
                progress_callback.emit(f"Message: {self.job.message}")
                old_message = self.job.message

            if self.job.status != pyeodh.ades.AdesJobStatus.RUNNING:
                break

            time.sleep(timeout)
        # self.stop_button.setEnabled(False) # ! ADES doesn't support job cancelling yet

    def handle_stop(self):
        # ! ADES does not support job cancel yet
        return

        def delete_job():
            self.job.delete()

        def deleted():
            self.log_msg("Job cancelled")

        worker = Worker(delete_job)
        worker.signals.finished.connect(deleted)
        self.threadpool.start(worker)

    def read_logs(self):
        fname = "/tmp/qgis-files/job-logs.json"
        if os.path.exists(fname):
            with open(fname, "r") as f:
                self.logs = json.load(f)

    def save_logs(self):
        if not os.path.exists("/tmp/qgis-files"):
            os.makedirs("/tmp/qgis-files")
        self.logs[self.job.id] = self.message_log.toPlainText()
        with open("/tmp/qgis-files/job-logs.json", "w+") as f:
            json.dump(self.logs, f)
