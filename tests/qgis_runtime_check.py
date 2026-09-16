"""Run with QGIS's python launcher; no network or purchases."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
from unittest.mock import patch

from qgis_test_support import finish

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qgis.core import Qgis, QgsApplication, QgsProject
from qgis.gui import QgsMapCanvas
from qgis.PyQt import QtCore, QtWidgets

from eodh_qgis.gui.hub_dock import HubDock

app = QgsApplication([], False)
app.initQgis()
window = QtWidgets.QMainWindow()
canvas = QgsMapCanvas()


class Interface:
    def mainWindow(self):
        return window

    def mapCanvas(self):
        return canvas


with patch.object(HubDock, "load_credentials", lambda self: None):
    dock = HubDock(Interface())
window.show()
dock.show()
app.processEvents()
assert [dock.tabs.tabText(i) for i in range(dock.tabs.count())] == ["Search", "Results", "Workspace"]
assert [dock.catalogue.itemText(i) for i in range(dock.catalogue.count())] == ["Public", "Commercial"]
item = {
    "id": "scene",
    "collection": "airbus-optical",
    "properties": {"datetime": "2026-07-01T00:00:00Z"},
    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
    "links": [
        {
            "rel": "self",
            "href": "https://eodatahub.org.uk/api/catalogue/stac/catalogs/commercial/catalogs/airbus/items/scene",
        }
    ],
    "assets": {"data": {"href": "https://example.test/data.tif", "type": "image/tiff"}},
}
dock.display_page({"features": [item]})
dock.set_bbox([0, 0, 1, 1])
app.processEvents()
assert len(dock.overlays.bands) == 1
assert len(QgsProject.instance().mapLayers()) == 0
assert dock.results.currentRow() == dock.timeline.index == 0
panel = dock.result_cards[0].commercial
panel.fields["country"].setText("GB")
assert panel.quote_button.isEnabled()
panel.quote_context, panel.quote = panel.context(), {"value": 10, "units": "GBP"}
panel.update_enabled()
assert panel.order_button.isEnabled()
panel.fields["bundle"].setCurrentText("Analytic")
assert panel.quote is None
assert not panel.order_button.isEnabled()
panel.quote_context, panel.quote = panel.context(), {"value": 10, "units": "GBP"}
panel.update_enabled()
dock.set_bbox([0, 0, 2, 2])
assert panel.quote is None
assert not panel.order_button.isEnabled()
# A response from an earlier request must remain invalid even if inputs change
# away and back to their original values while the request is in flight.
callbacks = []
original_submit = dock.submit
dock.client = object()
dock.submit = lambda title, work, done, failed=None, **kwargs: callbacks.append(done)
panel.get_quote()
panel.fields["country"].setText("FR")
panel.fields["country"].setText("GB")
callbacks.pop()({"value": 12, "units": "GBP"})
assert panel.quote is None
assert not panel.order_button.isEnabled()
panel.get_quote()
panel.set_item(item)
callbacks.pop()({"value": 12, "units": "GBP"})
assert panel.quote is None
assert not panel.busy
dock.submit = original_submit
dock.client = None
dock.show_footprints.setChecked(False)
assert not dock.overlays.bands
dock.show_footprints.setChecked(True)
assert len(dock.overlays.bands) == 1
dock.clear_results()
assert not dock.overlays.bands
for status, enabled in (("pending", False), ("failed", False), ("completed", True)):
    record = dict(item, _provider="Airbus", properties={"order:status": status})
    dock.records = [record]
    dock.filter_records()
    assert dock.record_cards[0].load_button.isEnabled() == enabled
dock.shutdown()
print(
    "PASS",
    Qgis.QGIS_VERSION,
    "Qt",
    QtCore.QT_VERSION_STR,
    "tabs, catalogue roots, geometry overlays, timeline, quote invalidation, workspace loading gates",
)
# Native QGIS owns globals until interpreter exit; avoid teardown ordering issues.
finish()
