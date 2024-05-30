import json
import os
import sys
import time
import traceback

import requests

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets, QtCore


# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "main_dialog.ui")
)


class WorkerSignals(QtCore.QObject):
    """
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    """

    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(tuple)
    result = QtCore.pyqtSignal(object)
    progress = QtCore.pyqtSignal(object)


class Worker(QtCore.QRunnable):
    """
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args
                     and kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    """

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        self.kwargs["progress_callback"] = self.signals.progress

    @QtCore.pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """

        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


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

        self.threadpool = QtCore.QThreadPool()

        self.usernameInput: QtWidgets.QLineEdit
        self.passwordInput: QtWidgets.QLineEdit
        self.processComboBox: QtWidgets.QComboBox
        self.inputsEdit: QtWidgets.QPlainTextEdit
        self.executeButton: QtWidgets.QPushButton
        self.responseBrowser: QtWidgets.QPlainTextEdit

        self.setup_process_box()
        self.executeButton.clicked.connect(self.handle_execute)

    def setup_process_box(self):
        self.processComboBox.addItem(
            "Convert url",
            userData={
                "id": "convert-url",
                "inputs": {
                    "fn": "resize",
                    "url": (
                        "https://eoepca.org/media_portal/images/logo6_med.original.png"
                    ),
                    "size": "50%",
                },
            },
        )
        self.processComboBox.addItem(
            "Water bodies",
            userData={
                "id": "water-bodies",
                "inputs": {
                    "stac_items": [
                        (
                            "https://test.eodatahub.org.uk/catalogue-data/"
                            "element84-data/collections/sentinel-2-c1-l2a/items/"
                            "S2B_T42MVU_20240319T054135_L2A.json"
                        )
                    ],
                    "aoi": "68.09, -6.42, 69.09, -5.43",
                    "epsg": "EPSG:4326",
                    "bands": ["green", "nir"],
                },
            },
        )
        self.processComboBox.currentIndexChanged.connect(self.handle_process_selection)
        self.selected_process = None

    def handle_process_selection(self, index):
        self.selected_process = self.processComboBox.itemData(index)
        self.inputsEdit.setPlainText(
            json.dumps(self.selected_process["inputs"], indent=2)
        )
        self.inputsEdit.setEnabled(True)

    def handle_execute(self):
        self.lock_form(True)
        self.username = self.usernameInput.text()
        self.password = self.passwordInput.text()

        warnings = []
        if not len(self.username):
            warnings.append("Enter a username.")
        if not len(self.password):
            warnings.append("Enter a password.")

        if self.selected_process is None:
            warnings.append("Select a process.")

        try:
            inputs = {"inputs": json.loads(self.inputsEdit.toPlainText())}
        except json.JSONDecodeError as e:
            warnings.append(f"Invalid JSON: Inputs\n{e}")
        if warnings:
            QtWidgets.QMessageBox.warning(self, "Invalid form!", "\n\n".join(warnings))
            self.lock_form(False)
            return

        url = (
            "https://test.eodatahub.org.uk/ades/test_cluster_3/ogc-api/processes/"
            f"{self.selected_process['id']}/execution"
        )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Prefer": "respond-async",
        }
        self.responseBrowser.appendPlainText(f"Sending request to: {url}")
        response = requests.post(
            url,
            headers=headers,
            auth=(self.username, self.password),
            data=json.dumps(inputs),
        )
        if not response.ok:
            self.responseBrowser.appendPlainText(
                f"Execute request failed with code {response.status_code}\n"
                f"{response.text}"
            )
            self.lock_form(False)
            return

        status_url = response.headers.get("Location")
        self.responseBrowser.appendPlainText(f"Status URL: {status_url}")
        self.responseBrowser.appendPlainText(f"Execute response:\n {response.json()}\n")

        worker = Worker(self.check_status, status_url)
        worker.signals.progress.connect(self.log_msg)
        worker.signals.finished.connect(lambda: self.lock_form(False))
        self.threadpool.start(worker)

    def log_msg(self, msg):
        self.responseBrowser.appendPlainText(msg)

    def check_status(self, status_url, progress_callback):
        timeout = 2
        progress_callback.emit(f"Checking job status (every {timeout}s)")
        old_status = ""
        old_message = ""

        while True:
            response = requests.get(
                status_url,
                headers={"Accept": "application/json"},
                auth=(self.username, self.password),
            )

            if not response.ok:
                progress_callback.emit(
                    f"Execute request failed with code {response.status_code}\n"
                    f"{response.text}"
                )
                return

            data = response.json()
            status = data["status"]
            message = data["message"]

            if status != old_status:
                progress_callback.emit(f"\nStatus: {status}")
                old_status = status

            if message != old_message:
                progress_callback.emit(f"Message: {message}")
                old_message = message

            if status != "running":
                break
            time.sleep(timeout)

    def lock_form(self, lock: bool):
        self.executeButton.setEnabled(not lock)
        self.usernameInput.setEnabled(not lock)
        self.passwordInput.setEnabled(not lock)
        self.processComboBox.setEnabled(not lock)
        self.inputsEdit.setEnabled(not lock)