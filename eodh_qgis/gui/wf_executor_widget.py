import os

from eodh_qgis.gui.job_details_widget import JobDetailsWidget
import pyeodh.ades

from qgis.PyQt import QtWidgets, uic

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/wf_executor.ui")
)


class WorkflowExecutorWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, process_id: str, ades_svc: pyeodh.ades.Ades, parent=None):
        """Constructor."""
        super(WorkflowExecutorWidget, self).__init__(parent)
        self.process = ades_svc.get_process(process_id)
        self.setupUi(self)
        self.input_map: dict[str, QtWidgets.QLineEdit] = {}

        self.vertical_layout_inputs: QtWidgets.QVBoxLayout
        self.cancel_button: QtWidgets.QPushButton
        self.execute_button: QtWidgets.QPushButton

        self.create_inputs()
        self.cancel_button.clicked.connect(self.handle_cancel)
        self.execute_button.clicked.connect(self.handle_execute)

    def handle_cancel(self):
        self.parent().removeWidget(self)
        self.parent().setCurrentIndex(0)

    def create_inputs(self):
        for k, v in self.process.inputs_schema.items():
            input_name = k
            input_default = v["schema"]["default"]
            input_type = v["schema"]["type"]
            input_desc = v["description"]

            horizontal_layout = QtWidgets.QHBoxLayout()

            label = QtWidgets.QLabel(f"{input_name} [{input_type}]")
            line_edit = QtWidgets.QLineEdit()
            line_edit.setText(input_default)
            line_edit.setToolTip(input_desc)

            self.input_map[k] = line_edit
            horizontal_layout.addWidget(label)
            horizontal_layout.addWidget(line_edit)

            self.vertical_layout_inputs.addLayout(horizontal_layout)

        self.show()

    def handle_execute(self):
        inputs = {}
        for k in self.process.inputs_schema.keys():
            inputs[k] = self.input_map[k].text().strip()

        job = self.process.execute({"inputs": inputs})
        self.parent().removeWidget(self)
        job_details = JobDetailsWidget(job=job, parent=self.parent())
        self.parent().addWidget(job_details)
        self.parent().setCurrentWidget(job_details)
        self.parent().parent().parent().jobs_widget.load_jobs()
