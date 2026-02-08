import json
import shutil
import tempfile
import time
from pathlib import Path

import pyeodh.ades
import pyeodh.resource_catalog
import requests
from qgis.core import QgsProject, QgsRasterLayer
from qgis.PyQt import QtCore, QtWidgets, uic

from eodh_qgis.worker import Worker

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(str(Path(__file__).parent.parent / "ui" / "job_detail.ui"))


def get_temp_dir():
    """Get a cross-platform temporary directory for QGIS plugin files."""
    temp_dir = Path(tempfile.gettempdir()) / "qgis-files"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


class JobDetailsWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, job: pyeodh.ades.Job, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.job = job
        self.outputs: list[pyeodh.resource_catalog.Item] = []
        self.setupUi(self)
        self.threadpool = QtCore.QThreadPool()
        self.logs = {}
        self.read_logs()

        self.table: QtWidgets.QTableWidget
        self.outputs_table: QtWidgets.QTableWidget
        self.message_log: QtWidgets.QTextBrowser
        self.close_button: QtWidgets.QPushButton
        self.stop_button: QtWidgets.QPushButton
        self.add_all_button: QtWidgets.QPushButton

        self.message_log.setText(self.logs.get(self.job.id))
        self.close_button.clicked.connect(self.handle_close)
        self.stop_button.clicked.connect(self.handle_stop)
        self.add_all_button.clicked.connect(self.handle_add_all)
        self.populate_table()

        if self.job.status in [
            pyeodh.ades.AdesJobStatus.RUNNING.value,
            pyeodh.ades.AdesJobStatus.ACCEPTED.value,
        ]:
            # self.stop_button.setEnabled(True) # ! ADES doesn't support job cancel yet
            self.trigger_polling()

        if self.job.status == pyeodh.ades.AdesJobStatus.SUCCESSFUL.value:
            self.fetch_outputs()

    def handle_close(self):
        self.parent().removeWidget(self)
        self.parent().setCurrentWidget(self.parent().parent().parent().button_widget_map["jobs"]["widget"])

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
        worker.signals.finished.connect(self.fetch_outputs)
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

            if self.job.status != pyeodh.ades.AdesJobStatus.RUNNING.value:
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
        logs_file = get_temp_dir() / "job-logs.json"
        if logs_file.exists():
            with logs_file.open("r") as f:
                self.logs = json.load(f)

    def save_logs(self):
        logs_file = get_temp_dir() / "job-logs.json"
        self.logs[self.job.id] = self.message_log.toPlainText()
        with logs_file.open("w+") as f:
            json.dump(self.logs, f)

    def populate_outputs_table(self, items: list[pyeodh.resource_catalog.Item]):
        self.outputs = items
        headers = ["Item ID", "Asset Name", "Asset URL"]
        self.outputs_table.setRowCount(len(items))
        self.outputs_table.setColumnCount(len(headers))
        self.outputs_table.setHorizontalHeaderLabels(headers)
        self.outputs_table.itemDoubleClicked.connect(self.handle_add_layer)
        for row_index, item in enumerate(items):
            self.outputs_table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(str(item.id)))
            name, asset = next(iter(item.assets.items()))
            self.outputs_table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(str(name)))
            self.outputs_table.setItem(row_index, 2, QtWidgets.QTableWidgetItem(str(asset.href)))
            header = self.outputs_table.horizontalHeader()
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)

        self.outputs_table.show()
        self.add_all_button.setEnabled(True)

    def fetch_outputs(self):
        def load_data(*args, **kwargs):
            return self.job.get_result_items()

        worker = Worker(load_data)
        worker.signals.result.connect(self.populate_outputs_table)
        self.threadpool.start(worker)

    def add_layer(self, item: pyeodh.resource_catalog.Item):
        temp_dir = get_temp_dir()

        def load_data(url: str, *args, **kwargs):
            local_filename = url.rsplit("/", maxsplit=1)[-1]
            path = temp_dir / local_filename
            print(f"Downloading {url} to {path}")
            with requests.get(
                url,
                stream=True,
                headers={"Authorization": f"Bearer {self.job._client.token}"},
            ) as r:
                print(r.status_code)
                with path.open("wb") as f:
                    shutil.copyfileobj(r.raw, f)
            rlayer = QgsRasterLayer(str(path), local_filename)
            QgsProject.instance().addMapLayer(rlayer, True)

        worker = Worker(load_data, next(iter(item.assets.values())).href)
        self.threadpool.start(worker)

    def handle_add_layer(self, table_item: QtWidgets.QTableWidgetItem):
        item = self.outputs[table_item.row()]
        self.add_layer(item)

    def handle_add_all(self):
        self.add_all_button.setDisabled(True)
        for item in self.outputs:
            self.add_layer(item)
