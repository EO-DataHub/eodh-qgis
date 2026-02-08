"""Dialog for selecting NetCDF variables to load."""

from __future__ import annotations

from qgis.PyQt import QtWidgets

from eodh_qgis.kerchunk_utils import NetCDFVariableInfo, get_variable_display_info


class VariableSelectionDialog(QtWidgets.QDialog):
    """Dialog for user to select which NetCDF variables to load."""

    def __init__(
        self,
        variables: list[NetCDFVariableInfo],
        item_id: str,
        asset_key: str,
        parent: QtWidgets.QWidget | None = None,
    ):
        """Initialize the dialog.

        Args:
            variables: List of available variables
            item_id: STAC item ID for display
            asset_key: Asset key for display
            parent: Parent widget
        """
        super().__init__(parent)
        self.variables = variables
        self._checkboxes: list[tuple[QtWidgets.QCheckBox, str]] = []
        self._setup_ui(item_id, asset_key)

    def _setup_ui(self, item_id: str, asset_key: str) -> None:
        """Build the dialog UI."""
        self.setWindowTitle(f"Select Variables - {item_id}")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        layout = QtWidgets.QVBoxLayout(self)

        # Info label
        info_label = QtWidgets.QLabel(
            f"Found {len(self.variables)} data variables in {asset_key}.\nSelect which variables to load as layers:"
        )
        layout.addWidget(info_label)

        # Scroll area with checkboxes
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)

        for var in self.variables:
            display_text = get_variable_display_info(var)
            checkbox = QtWidgets.QCheckBox(display_text)
            checkbox.setChecked(True)  # Default to selected
            checkbox.setToolTip(self._build_tooltip(var))
            self._checkboxes.append((checkbox, var.name))
            scroll_layout.addWidget(checkbox)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Select All / Deselect All buttons
        btn_layout = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton("Select All")
        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        select_all_btn.clicked.connect(self._select_all)
        deselect_all_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        layout.addLayout(btn_layout)

        # OK / Cancel
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _build_tooltip(self, var: NetCDFVariableInfo) -> str:
        """Build detailed tooltip for variable."""
        lines = [f"Name: {var.name}"]
        if var.long_name:
            lines.append(f"Long name: {var.long_name}")
        if var.standard_name:
            lines.append(f"Standard name: {var.standard_name}")
        if var.units:
            lines.append(f"Units: {var.units}")
        lines.append(f"Shape: {var.shape}")
        lines.append(f"Dimensions: {var.dimensions}")
        return "\n".join(lines)

    def _select_all(self) -> None:
        """Select all checkboxes."""
        for cb, _ in self._checkboxes:
            cb.setChecked(True)

    def _deselect_all(self) -> None:
        """Deselect all checkboxes."""
        for cb, _ in self._checkboxes:
            cb.setChecked(False)

    def get_selected_variables(self) -> list[str]:
        """Return list of selected variable names."""
        return [name for cb, name in self._checkboxes if cb.isChecked()]
