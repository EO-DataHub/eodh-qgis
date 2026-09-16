"""Exercise screen transitions with real Qt/QGIS widgets and no network."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qgis.core import Qgis, QgsApplication, QgsFeature, QgsGeometry, QgsProject, QgsVectorFileWriter, QgsVectorLayer
from qgis.gui import QgsMapCanvas
from qgis.PyQt import QtCore, QtGui, QtWidgets

from eodh_qgis.gui.hub_dock import HubDock

app = QgsApplication([], False)
app.initQgis()
window, canvas = QtWidgets.QMainWindow(), QgsMapCanvas()


class Interface:
    def mainWindow(self):
        return window

    def mapCanvas(self):
        return canvas


with patch.object(HubDock, "load_credentials", lambda self: None):
    dock = HubDock(Interface())
window.resize(900, 850)
window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
dock.stack.setCurrentWidget(dock.tabs)
window.show()
app.processEvents()


# Controls must never appear as native top-level windows during asynchronous
# result/workspace population (even briefly before a layout adopts them).
class UnexpectedWindows(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.shown = []

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Show and isinstance(obj, QtWidgets.QWidget) and obj.isWindow():
            self.shown.append(type(obj).__name__)
        return False


window_watch = UnexpectedWindows()
app.installEventFilter(window_watch)
assert dock.collection.maxVisibleItems() == 20

entry = {
    "collection": {
        "id": "sentinel2_ard",
        "extent": {"spatial": {"bbox": [[0, 0, 2, 2]]}, "temporal": {"interval": [["2015-07-08T00:00:00Z", None]]}},
    }
}
dock.collection.addItem("Sentinel 2 ARD", entry)
assert dock.start.date() == QtCore.QDate(2015, 7, 8)
assert dock.end.date() == QtCore.QDate.currentDate()
assert dock.bbox == [0, 0, 2, 2]
assert dock.search_button.isEnabled()
dock.clear_aoi_button.click()
assert not dock.search_button.isEnabled()
assert dock.aoi_text.text() == "No area selected"
dock.collection_changed()
scene = {
    "id": "old",
    "collection": "sentinel2_ard",
    "bbox": [0, 0, 1, 1],
    "properties": {"datetime": "2026-01-01T00:00:00Z"},
    "links": [{"rel": "self", "href": "https://example.test/items/old"}],
    "assets": {
        "cog": {"href": "https://example.test/data.tif", "type": "image/tiff"},
        "thumbnail": {"href": "https://example.test/thumb.png", "type": "image/png"},
    },
}
new = deepcopy(scene)
new.update(id="new", properties={"datetime": "2026-09-01T00:00:00Z"})
outside = dict(scene, id="outside", bbox=[10, 10, 11, 11])
undated = dict(scene, id="undated", properties={})
first = {
    "features": [scene, outside, new, undated],
    "numberMatched": 101,
    "links": [{"rel": "next", "href": "https://example.test/page2"}],
}
dock.pages = [first]
dock.display_page(first)
dock.tabs.setCurrentIndex(1)
app.processEvents()
assert len(dock.items) == 3
assert "1 outside AOI excluded" in dock.summary.text()
assert dock.timeline.order == [0, 1]
assert dock.results.currentRow() == 1
dock.timeline.previous.click()
assert dock.results.currentRow() == dock.timeline.index == 0
card = dock.result_cards[0]
assert [key for key, asset in card.assets.selected()] == ["cog"]
assert not card.quick.isHidden()
assert card.asset_panel.isHidden()
card.expand.click()
app.processEvents()
assert not card.asset_panel.isHidden()
date_label = dock.timeline.images[0]
assert date_label.text() == "01/01"
assert date_label.height() >= 12
assert date_label.isVisible(), str(
    (date_label.geometry(), date_label.parentWidget().geometry(), date_label.parentWidget().isVisible())
)
portrait = QtGui.QPixmap(30, 90)
portrait.fill(QtGui.QColor("blue"))
dock.timeline.set_thumbnail(0, portrait)
assert date_label.icon().actualSize(QtCore.QSize(56, 42)) == QtCore.QSize(56, 42)
assert card.height() >= card.layout().minimumSize().height()

# Forward/back navigation keeps the original total even if the next page omits it.
second = {"features": [new], "numberMatched": None, "context": {"matched": None}}
dock.pages.append(second)
dock.next_page()
assert dock.page_index == 1
assert dock.total_count == 101
assert dock.page_label.text() == "Page 2 of 3"
dock.previous_page()
assert dock.page_index == 0
dock.pages = [first]
dock.client = object()
original_submit = dock.submit
pending = []
dock.submit = lambda title, work, done, failed=None, **kwargs: pending.append((work, done, failed))
dock.next_page()
pending.pop()[2]("Service unavailable")
assert dock.page_index == 0
assert len(dock.items) == 3
assert dock.pagination_error.text() == "Could not load page 2: Service unavailable"
dock.client = None

# Separate cards own separate quotes. Declining confirmation must never submit an order.
commercial = deepcopy(scene)
commercial.update(
    collection="airbus-optical",
    links=[{"rel": "self", "href": "https://eodatahub.org.uk/catalogs/commercial/catalogs/airbus/items/one"}],
)
dock.page_index = 0
dock.display_page({"features": [commercial, dict(commercial, id="two")], "numberMatched": None, "numMatched": None})
assert dock.total_count == 2
one, two = [card.commercial for card in dock.result_cards]
one.quote_context, one.quote = one.context(), {"value": 1234.5, "units": "GBP"}
one.update_enabled()
assert one.quote_text.text() == "1,234.50 GBP"
assert one.order_button.isEnabled()
assert not two.order_button.isEnabled()
with patch.object(
    QtWidgets.QMessageBox, "warning", return_value=QtWidgets.QMessageBox.StandardButton.No
) as confirmation:
    one.place_order()
assert not pending
assert "This action is irreversible." in confirmation.call_args.args[2]
assert confirmation.call_args.args[1] == "EODH — Confirm Order"
one.fields["country"].setText("FR")
assert one.quote is None

# Workspace filtering retains asset selections and expansion state.
record = dict(
    commercial, _provider="Airbus", _collection_label="Airbus SPOT Data", properties={"order:status": "succeeded"}
)
dock.records = [record, dict(record, id="pending", properties={"order:status": "pending"})]
dock.filter_records()
delivered = dock.record_cards[0]
delivered.expand.setChecked(True)
delivered.assets.boxes[0][0].setChecked(False)
dock.filter_records()
assert dock.record_cards[0].expand.isChecked()
assert not dock.record_cards[0].assets.selected()
assert not dock.record_cards[1].can_load

# Imported projected vector bounds are transformed without adding project layers.
with tempfile.TemporaryDirectory() as directory:
    vector = QgsVectorLayer("Polygon?crs=EPSG:3857", "AOI", "memory")
    feature = QgsFeature()
    feature.setGeometry(
        QgsGeometry.fromWkt("POLYGON((0 0,111319.490793 0,111319.490793 111325.142866,0 111325.142866,0 0))")
    )
    vector.dataProvider().addFeatures([feature])
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    path = str(Path(directory) / "area.gpkg")
    result = QgsVectorFileWriter.writeAsVectorFormatV3(vector, path, QgsProject.instance().transformContext(), options)
    assert result[0] == QgsVectorFileWriter.WriterError.NoError
    dock.import_aoi_path(path)
    assert all(abs(a - b) < 0.00001 for a, b in zip(dock.bbox, [0, 0, 1, 1]))
    assert "area.gpkg" in dock.aoi_text.text()
    assert not QgsProject.instance().mapLayers()
    second_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "second", "memory")
    feature.setGeometry(QgsGeometry.fromWkt("POLYGON((2 2,3 2,3 3,2 3,2 2))"))
    second_layer.dataProvider().addFeatures([feature])
    options.layerName = "second"
    options.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        second_layer, path, QgsProject.instance().transformContext(), options
    )
    assert result[0] == QgsVectorFileWriter.WriterError.NoError
    dock.import_aoi_path(path)
    assert all(abs(a - b) < 0.00001 for a, b in zip(dock.bbox, [0, 0, 3, 3]))

assert not window_watch.shown, window_watch.shown
app.removeEventFilter(window_watch)

dock.submit = original_submit
dock.shutdown()
print(
    "PASS",
    Qgis.QGIS_VERSION,
    "screen defaults, AOI gates/import, inline cards, timeline dates, paging failure/cache, independent quotes, purchase cancellation, workspace state",
)
sys.stdout.flush()
os._exit(0)
