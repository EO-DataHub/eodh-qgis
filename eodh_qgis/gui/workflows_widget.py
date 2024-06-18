import os

import pyeodh.ades
from qgis.PyQt import QtCore, QtWidgets, uic

from eodh_qgis.gui.wf_editor_widget import WorkflowEditorWidget
from eodh_qgis.gui.wf_executor_widget import WorkflowExecutorWidget
from eodh_qgis.worker import Worker
import requests

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/workflows.ui")
)


class WorkflowsWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, ades_svc: pyeodh.ades.Ades, parent=None):
        """Constructor."""
        super(WorkflowsWidget, self).__init__(parent)
        self.setupUi(self)
        self.ades_svc = ades_svc
        self.processes: list[pyeodh.ades.Process] = []
        self.row_selected = False
        self.threadpool = QtCore.QThreadPool()
        self.new_button: QtWidgets.QPushButton
        self.edit_button: QtWidgets.QPushButton
        self.execute_button: QtWidgets.QPushButton
        self.refresh_button: QtWidgets.QPushButton
        self.remove_button: QtWidgets.QPushButton
        self.table: QtWidgets.QTableWidget

        self.table.cellClicked.connect(self.handle_table_click)
        self.new_button.clicked.connect(self.handle_new)
        self.edit_button.clicked.connect(self.handle_new)
        self.execute_button.clicked.connect(self.handle_execute)
        self.refresh_button.clicked.connect(self.load_workflows)
        self.remove_button.clicked.connect(self.handle_remove)

        self.load_workflows()

    def handle_new(self):
        editor = WorkflowEditorWidget(ades_svc=self.ades_svc, parent=self.parent())
        self.parent().addWidget(editor)
        self.parent().setCurrentWidget(editor)

    def handle_execute(self):
        selected_rows = self.table.selectionModel().selectedRows()
        process = self.processes[selected_rows[0].row()]
        executor = WorkflowExecutorWidget(
            process_id=process.id,
            ades_svc=self.ades_svc,
            parent=self.parent(),
        )
        self.parent().addWidget(executor)
        self.parent().setCurrentWidget(executor)

    def handle_table_click(self, row, col):
        self.row_selected = True
        self.execute_button.setEnabled(True)
        self.edit_button.setEnabled(True)
        self.remove_button.setEnabled(True)

    def populate_table(self, processes: list[pyeodh.ades.Process]):
        self.processes = processes
        headers = {
            "id": "ID",
            "title": "Title",
            "description": "Description",
            "version": "Version",
            "keywords": "Keywords",
        }
        self.table.setRowCount(len(processes))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(list(headers.values()))

        for row_index, proc in enumerate(processes):
            for col_index, key in enumerate(headers.keys()):
                self.table.setItem(
                    row_index,
                    col_index,
                    QtWidgets.QTableWidgetItem(str(getattr(proc, key, ""))),
                )

        self.table.show()

    def load_workflows(self):
        self.lock_form(True)

        def load_data(*args, **kwargs):
            return self.ades_svc.get_processes()

        worker = Worker(load_data)
        worker.signals.result.connect(self.populate_table)
        worker.signals.finished.connect(lambda: self.lock_form(False))
        self.threadpool.start(worker)

    def lock_form(self, locked: bool):
        self.new_button.setEnabled(not locked)
        self.edit_button.setEnabled(not locked and self.row_selected)
        self.execute_button.setEnabled(not locked and self.row_selected)
        self.remove_button.setEnabled(not locked and self.row_selected)
        self.table.setEnabled(not locked)

    def handle_remove(self):
        self.lock_form(True)
        selected_rows = self.table.selectionModel().selectedRows()
        process = self.processes[selected_rows[0].row()]
        try:
            process.delete()
        except requests.HTTPError as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Error un-deploying process {process.id}!\n{e}"
            )
        else:
            QtWidgets.QMessageBox.information(
                self, "Success", f"Successfully un-deployed {process.id}."
            )
        finally:
            self.load_workflows()
