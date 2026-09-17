"""Qt5/Qt6 widgets for the ArcGIS-aligned EODH experience."""

from qgis.PyQt import QtCore, QtGui, QtWidgets

from eodh_qgis.api.hub import OPTICAL_BUNDLES, OPTICAL_LICENCES, SAR_LICENCES, PurchaseContext, href, provider

from .hub_scroll import ScrollComboBox


def label(text):
    widget = QtWidgets.QLabel(text)
    widget.setWordWrap(True)
    widget.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    return widget


def button(text, callback, primary=False):
    widget = QtWidgets.QPushButton(text)
    widget.clicked.connect(callback)
    if primary:
        widget.setObjectName("primary")
    return widget


class CommercialPanel(QtWidgets.QFrame):
    changed = QtCore.pyqtSignal()

    def __init__(self, dock):
        super().__init__()
        self.setObjectName("purchasePanel")
        self.setStyleSheet(
            "QFrame#purchasePanel {background:rgba(255,215,0,16);border-radius:3px;} QFrame#purchasePanel QWidget {font-size:10px;}"
        )
        self.dock, self.item, self.quote_context, self.quote = dock, {}, None, None
        self.busy = False
        self.revision = 0
        self.request_id = 0
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        self.provider_label = label("")
        self.provider_label.setStyleSheet("color:#b8860b;")
        font = self.provider_label.font()
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        self.provider_label.setFont(font)
        layout.addWidget(self.provider_label)
        self.fields = {}
        self.field_rows = {}
        for key, title in (
            ("licence", "Licence:"),
            ("bundle", "Bundle:"),
            ("country", "Country:"),
            ("orbit", "Orbit:"),
            ("resolution", "Resolution:"),
            ("projection", "Projection:"),
        ):
            group = QtWidgets.QWidget()
            row = QtWidgets.QHBoxLayout(group)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            row.addWidget(label(title))
            widget = QtWidgets.QLineEdit() if key == "country" else ScrollComboBox()
            self.fields[key] = widget
            widget.setMinimumWidth(40 if key == "country" else 120 if key in ("licence", "bundle") else 100)
            if key == "country":
                widget.setMaximumWidth(50)
                widget.setMaxLength(3)
            row.addWidget(widget)
            row.addStretch()
            self.field_rows[key] = group
            layout.addWidget(group)
            (widget.textChanged if key == "country" else widget.currentTextChanged).connect(self.invalidate)
        quote_row = QtWidgets.QHBoxLayout()
        self.quote_button = button("Get Quote", self.get_quote)
        quote_row.addWidget(self.quote_button)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedSize(60, 2)
        self.progress.hide()
        quote_row.addWidget(self.progress)
        self.quote_text = label("")
        quote_row.addWidget(self.quote_text)
        quote_row.addStretch()
        layout.addLayout(quote_row)
        self.message = label("")
        self.message.setStyleSheet("color:#666;")
        layout.addWidget(self.message)
        self.order_group = QtWidgets.QWidget()
        order_layout = QtWidgets.QVBoxLayout(self.order_group)
        order_layout.setContentsMargins(0, 0, 0, 0)
        order_layout.setSpacing(4)
        self.help = label("")
        self.help.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.help.setText(
            '<a href="https://docs.eodatahub.org.uk/Getting-Started/workspaces/linked-accounts/" style="color:#006a8a;text-decoration:none;">Provider account and licensing guidance</a>'
        )
        self.help.setOpenExternalLinks(True)
        order_layout.addWidget(self.help)
        self.order_button = button("Purchase", self.place_order)
        order_layout.addWidget(self.order_button, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.order_group)
        self.purchase_status = label("")
        self.purchase_status.setStyleSheet("color:green;")
        layout.addWidget(self.purchase_status)
        self.purchase_error = label("")
        self.purchase_error.setStyleSheet("color:red;")
        layout.addWidget(self.purchase_error)
        self.update_enabled()

    def set_item(self, item):
        self.request_id += 1
        self.busy = False
        self.item = item or {}
        p = provider(self.item)
        self.provider_label.setText(
            "Commercial ("
            + {"Airbus Optical": "AirbusOptical", "Airbus SAR": "AirbusSar", "Open Cosmos": "OpenCosmos"}.get(p, p)
            + ")"
        )
        choices = {
            "licence": SAR_LICENCES if p == "Airbus SAR" else OPTICAL_LICENCES,
            "bundle": ("SSC", "MGD", "GEC", "EEC") if p == "Airbus SAR" else OPTICAL_BUNDLES,
            "orbit": ("rapid", "science"),
            "resolution": ("RE", "SE"),
            "projection": ("Auto", "UTM", "UPS"),
        }
        for key, widget in self.fields.items():
            widget.blockSignals(True)
            if key != "country":
                widget.clear()
                widget.addItems(choices[key])
            else:
                widget.setText("GB" if p == "Airbus Optical" else "")
            widget.blockSignals(False)
        self.invalidate()

    def context(self):
        p = provider(self.item)
        values = {k: w.text().strip() if k == "country" else w.currentText() for k, w in self.fields.items()}
        if not p.startswith("Airbus"):
            values["licence"] = ""
        if p != "Airbus Optical":
            values["country"] = ""
        if p != "Airbus SAR":
            for key in ("orbit", "resolution", "projection"):
                values[key] = ""
        else:
            if values["bundle"] == "SSC":
                values["resolution"] = ""
            if values["bundle"] in ("SSC", "MGD"):
                values["projection"] = ""
        if p == "Open Cosmos":
            values["bundle"] = ""
        return PurchaseContext(
            href(self.item, "self") or "", p, tuple(self.dock.bbox) if self.dock.bbox else None, **values
        )

    def invalidate(self, *args):
        self.revision += 1
        self.quote_context, self.quote = None, None
        self.message.clear()
        self.purchase_status.clear()
        p = provider(self.item)
        bundle = self.fields["bundle"].currentText()
        visible = {
            "licence": p.startswith("Airbus"),
            "bundle": p in ("Airbus Optical", "Airbus SAR", "Planet"),
            "country": p == "Airbus Optical",
            "orbit": p == "Airbus SAR",
            "resolution": p == "Airbus SAR" and bundle != "SSC",
            "projection": p == "Airbus SAR" and bundle not in ("SSC", "MGD"),
        }
        for key in self.fields:
            self.field_rows[key].setVisible(visible[key])
        self.update_enabled()

    def update_enabled(self, *args):
        try:
            context = self.context()
            context.requests()
            valid = bool(context.item_url)
        except ValueError:
            valid = False
        self.quote_button.setEnabled(valid and not self.busy)
        self.order_button.setEnabled(
            valid and not self.busy and self.quote is not None and self.quote_context == self.context()
        )
        self.order_group.setVisible(self.quote is not None)
        self.quote_text.setText(f"{self.quote['value']:,.2f} {self.quote['units']}" if self.quote else "")
        self.progress.setVisible(self.busy)
        for widget in (self.message, self.purchase_status, self.purchase_error):
            widget.setVisible(bool(widget.text()))
        self.changed.emit()

    def get_quote(self):
        if self.busy or not self.dock.client:
            return
        context = self.context()
        try:
            payload, _ = context.requests()
        except ValueError as error:
            self.purchase_error.setText(str(error))
            return
        self.invalidate()
        self.purchase_error.clear()
        self.busy = True
        self.request_id += 1
        request_id, revision = self.request_id, self.revision
        self.update_enabled()
        client = self.dock.client

        def done(result):
            if request_id != self.request_id:
                return
            self.busy = False
            if revision == self.revision and context == self.context():
                if not isinstance(result.get("value"), (float, int)) or not result.get("units"):
                    self.purchase_error.setText("EODH returned an invalid quote. Retry.")
                else:
                    self.quote_context, self.quote = context, result
                    self.message.setText(result.get("message") or "")
            self.update_enabled()

        def failed(error):
            if request_id != self.request_id:
                return
            self.busy = False
            self.invalidate()
            self.purchase_error.setText(str(error))
            self.update_enabled()

        self.dock.submit(
            "Getting quote…",
            lambda: client.request(context.item_url.rstrip("/") + "/quote", "POST", payload),
            done,
            failed,
            quiet=True,
        )

    def place_order(self):
        if not self.order_button.isEnabled() or self.quote_context != self.context():
            return
        context, current_quote = self.context(), self.quote
        if current_quote is None:
            return
        answer = QtWidgets.QMessageBox.warning(
            self,
            "EODH — Confirm Order",
            f"You are about to order this item for {current_quote['value']:,.2f} {current_quote['units']}.\n\n"
            "This action is irreversible. Do you want to proceed?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes or context != self.context():
            return
        _, payload = context.requests()
        self.busy = True
        self.request_id += 1
        request_id = self.request_id
        self.update_enabled()
        client = self.dock.client

        def done(result):
            if request_id != self.request_id:
                return
            self.busy = False
            self.invalidate()
            self.purchase_status.setText("Ordered — check workspace for delivery status")
            self.update_enabled()

        def failed(error):
            if request_id != self.request_id:
                return
            self.busy = False
            self.invalidate()
            self.purchase_error.setText(str(error))
            self.update_enabled()

        self.dock.submit(
            "Placing order…",
            lambda: client.request(context.item_url.rstrip("/") + "/order", "POST", payload, raw=True),
            done,
            failed,
            quiet=True,
        )
