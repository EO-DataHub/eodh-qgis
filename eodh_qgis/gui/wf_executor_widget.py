import os

import pyeodh.ades
from qgis.PyQt import QtCore, QtWidgets, uic

from eodh_qgis.gui.job_details_widget import JobDetailsWidget

# This loads your .ui file so that PyQt can populate your plugin with the elements from
# Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "../ui/wf_executor.ui"))


class WorkflowExecutorWidget(QtWidgets.QWidget, FORM_CLASS):
    def __init__(self, process_id: str, ades_svc: pyeodh.ades.Ades, parent=None):
        """Constructor."""
        super().__init__(parent)
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
            input_default = v["schema"].get("default", "")
            input_type = v["schema"].get("type", "")
            input_desc = v.get("description", "")

            # Check for array input
            is_array = (
                v.get("extended-schema", {}).get("type") == "array"
                and v.get("extended-schema", {}).get("items", {}).get("type") == "string"
            )

            horizontal_layout = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(f"{input_name} ({input_type}{'[]' if is_array else ''})")
            horizontal_layout.addWidget(label)

            if is_array:
                label.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
                label.setContentsMargins(0, 12, 0, 0)  # Add a small top margin
                # Widget to hold multiple QLineEdits, each with its own remove button
                array_widget = QtWidgets.QWidget()
                array_layout = QtWidgets.QVBoxLayout()
                array_widget.setLayout(array_layout)
                line_edits = []

                # Add button to add new line edits (always at the bottom)
                btn_layout = QtWidgets.QHBoxLayout()
                btn_layout.addStretch()  # Add stretch first to push the button right
                add_btn = QtWidgets.QPushButton("+")
                btn_layout.addWidget(add_btn)
                btn_widget = QtWidgets.QWidget()
                btn_widget.setLayout(btn_layout)
                array_layout.addWidget(btn_widget)

                def add_line_edit(default_text=""):
                    row_widget = QtWidgets.QWidget()
                    row_layout = QtWidgets.QHBoxLayout()
                    row_layout.setContentsMargins(0, 0, 0, 0)
                    le = QtWidgets.QLineEdit()
                    le.setText(default_text)
                    le.setToolTip(input_desc)
                    remove_btn = QtWidgets.QPushButton("x")
                    remove_btn.setFixedWidth(24)
                    row_layout.addWidget(le)
                    row_layout.addWidget(remove_btn)
                    row_widget.setLayout(row_layout)
                    # Insert above the add button (which is always last)
                    array_layout.insertWidget(array_layout.count() - 1, row_widget)
                    line_edits.append((le, row_widget))

                    def handle_remove():
                        if len(line_edits) > 1:
                            array_layout.removeWidget(row_widget)
                            row_widget.deleteLater()
                            line_edits.remove((le, row_widget))

                    remove_btn.clicked.connect(handle_remove)
                    return le

                # Add at least one line edit (or more if default is a list)
                if isinstance(input_default, list):
                    for val in input_default:
                        add_line_edit(val)
                else:
                    add_line_edit(input_default)

                def handle_add():
                    add_line_edit("")

                add_btn.clicked.connect(handle_add)

                self.input_map[k] = line_edits  # Store the list of (QLineEdit, row_widget)
                horizontal_layout.addWidget(array_widget)
            else:
                line_edit = QtWidgets.QLineEdit()
                line_edit.setText(input_default)
                line_edit.setToolTip(input_desc)
                self.input_map[k] = line_edit
                horizontal_layout.addWidget(line_edit)

            self.vertical_layout_inputs.addLayout(horizontal_layout)

        self.show()

    def handle_execute(self):
        inputs = {}
        for k, v in self.process.inputs_schema.items():
            # Check for array input
            is_array = (
                v.get("extended-schema", {}).get("type") == "array"
                and v.get("extended-schema", {}).get("items", {}).get("type") == "string"
            )
            if is_array:
                # Collect all non-empty values from the list of QLineEdits
                line_edits = self.input_map[k]
                values = [le.text().strip() for le, _ in line_edits if le.text().strip()]
                inputs[k] = values
            else:
                inputs[k] = self.input_map[k].text().strip()
        print(inputs)
        job = self.process.execute(inputs)
        self.parent().removeWidget(self)
        job_details = JobDetailsWidget(job=job, parent=self.parent())
        self.parent().addWidget(job_details)
        self.parent().setCurrentWidget(job_details)
        self.parent().parent().parent().button_widget_map["jobs"]["widget"].load_jobs()
        self.parent().parent().parent().style_menu_button(self.parent().parent().parent().jobs_button)
