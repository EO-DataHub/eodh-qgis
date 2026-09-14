"""Qt5/Qt6 widgets for the ArcGIS-aligned EODH experience."""

from datetime import datetime

from qgis.PyQt import QtCore, QtGui, QtWidgets

from eodh_qgis.api.hub import OPTICAL_BUNDLES, OPTICAL_LICENCES, SAR_LICENCES, PurchaseContext, href, provider


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


class Timeline(QtWidgets.QWidget):
    selected = QtCore.pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.items, self.points, self.index = [], [], -1
        self.setMinimumHeight(90)
        self.setMouseTracking(True)

    def set_items(self, items):
        self.items = items
        self.index = -1
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(self.palette().text().color())
        painter.drawText(10, 17, "Acquisition timeline")
        self.points = []
        dates = []
        for index, item in enumerate(self.items):
            raw = (item.get("properties") or {}).get("datetime")
            if not isinstance(raw, str):
                continue
            try:
                dates.append((index, datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp(), raw[:10]))
            except (TypeError, ValueError, AttributeError):
                pass
        if not dates:
            painter.drawText(10, 53, "No dated results")
            return
        low, high = min(x[1] for x in dates), max(x[1] for x in dates)
        painter.drawLine(15, 47, self.width() - 15, 47)
        for index, timestamp, text in dates:
            x = 15 + (timestamp - low) / (high - low or 1) * (self.width() - 30)
            y = 43 - (index % 3) * 8
            self.points.append((index, x, y, text))
            painter.setBrush(QtGui.QColor("#d88a26" if index == self.index else "#4c72ba"))
            painter.drawEllipse(QtCore.QPointF(x, y), 5 if index == self.index else 3, 5 if index == self.index else 3)
        painter.drawText(10, 75, min(dates, key=lambda x: x[1])[2])
        painter.drawText(max(10, self.width() - 85), 75, max(dates, key=lambda x: x[1])[2])

    def mousePressEvent(self, event):
        if self.points:
            point = min(self.points, key=lambda p: (p[1] - event.pos().x()) ** 2 + (p[2] - event.pos().y()) ** 2)
            self.selected.emit(point[0])

    def mouseMoveEvent(self, event):
        if self.points:
            point = min(self.points, key=lambda p: abs(p[1] - event.pos().x()))
            self.setToolTip(point[3] + "\n" + self.items[point[0]].get("id", ""))


class CommercialPanel(QtWidgets.QGroupBox):
    def __init__(self, dock):
        super().__init__("Commercial quote and order")
        self.dock, self.item, self.quote_context, self.quote = dock, {}, None, None
        self.busy = False
        self.revision = 0
        self.request_id = 0
        self.form = QtWidgets.QFormLayout(self)
        self.provider_label = label("")
        self.form.addRow(self.provider_label)
        self.fields = {}
        for key, title in (
            ("licence", "Licence"),
            ("bundle", "Product bundle"),
            ("country", "End-user country"),
            ("orbit", "Orbit"),
            ("resolution", "Resolution"),
            ("projection", "Projection"),
        ):
            widget = QtWidgets.QLineEdit() if key == "country" else QtWidgets.QComboBox()
            self.fields[key] = widget
            self.form.addRow(title, widget)
            (widget.textChanged if key == "country" else widget.currentTextChanged).connect(self.invalidate)
        self.fields["country"].setPlaceholderText("e.g. United Kingdom")
        self.help = label("")
        self.help.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.help.setText(
            '<a href="https://docs.eodatahub.org.uk/Analysts/commercial/ordering-commercial-data/#understanding-the-ordering-options">Commercial bundles and licences</a>'
        )
        self.help.setOpenExternalLinks(True)
        self.form.addRow(self.help)
        self.quote_button = button("Get Quote", self.get_quote)
        self.form.addRow(self.quote_button)
        self.message = label("Get a quote to review the price.")
        self.form.addRow(self.message)
        self.accept = QtWidgets.QCheckBox("I accept the applicable licensing terms")
        self.accept.toggled.connect(self.update_enabled)
        self.form.addRow(self.accept)
        self.order_button = button("Place Order", self.place_order, True)
        self.form.addRow(self.order_button)

    def set_item(self, item):
        self.request_id += 1
        self.busy = False
        self.item = item or {}
        p = provider(self.item)
        self.provider_label.setText(p)
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
                widget.clear()
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
        self.accept.setChecked(False)
        self.message.setText("Get a new quote after changing any ordering option.")
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
        for key, widget in self.fields.items():
            widget.setVisible(visible[key])
            self.form.labelForField(widget).setVisible(visible[key])
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
            valid
            and not self.busy
            and self.quote is not None
            and self.quote_context == self.context()
            and self.accept.isChecked()
        )

    def get_quote(self):
        if self.busy or not self.dock.client:
            return
        context = self.context()
        try:
            payload, _ = context.requests()
        except ValueError as error:
            self.message.setText(str(error))
            return
        self.invalidate()
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
                    self.message.setText("EODH returned an invalid quote. Retry.")
                else:
                    self.quote_context, self.quote = context, result
                    self.message.setText(f"{result['value']} {result['units']}\n{result.get('message') or ''}")
            self.update_enabled()

        def failed(error):
            if request_id != self.request_id:
                return
            self.busy = False
            self.invalidate()
            self.message.setText(str(error))

        self.dock.submit(
            "Getting quote…",
            lambda: client.request(context.item_url.rstrip("/") + "/quote", "POST", payload),
            done,
            failed,
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
            f"Order {self.item.get('id')} for {current_quote['value']} {current_quote['units']}?\n\nThis purchase is irreversible.",
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
            self.message.setText("Ordered — check Workspace for delivery status.")

        def failed(error):
            if request_id != self.request_id:
                return
            self.busy = False
            self.invalidate()
            self.message.setText(str(error) + "\nCheck Workspace before attempting another order.")

        self.dock.submit(
            "Placing order…",
            lambda: client.request(context.item_url.rstrip("/") + "/order", "POST", payload, raw=True),
            done,
            failed,
        )
