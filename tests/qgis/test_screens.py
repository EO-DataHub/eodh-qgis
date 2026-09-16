from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from qgis.core import QgsFeature, QgsGeometry, QgsProject, QgsVectorFileWriter, QgsVectorLayer
from qgis.PyQt import QtCore, QtGui, QtWidgets

from eodh_qgis.raster_loader import StreamingUnavailable


class UnexpectedWindows(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.shown = []

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Show and isinstance(obj, QtWidgets.QWidget) and obj.isWindow():
            self.shown.append(type(obj).__name__)
        return False


@pytest.fixture(autouse=True)
def no_loading_windows(dock, qgis_app):
    watch = UnexpectedWindows()
    qgis_app.installEventFilter(watch)
    yield
    qgis_app.removeEventFilter(watch)
    assert not watch.shown, watch.shown


@pytest.fixture
def results_page(dock, scene, qgis_app):
    dock.set_bbox([0, 0, 2, 2])
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
    qgis_app.processEvents()
    return first, new


def test_collection_defaults_and_clear_aoi(dock, collection_entry):
    assert dock.collection.maxVisibleItems() == 20
    entry = collection_entry
    dock.collection.addItem("Sentinel 2 ARD", entry)
    assert dock.start.date() == QtCore.QDate(2015, 7, 8)
    assert dock.end.date() == QtCore.QDate.currentDate()
    assert dock.bbox == [0, 0, 2, 2]
    assert dock.search_button.isEnabled()
    dock.clear_aoi_button.click()
    assert not dock.search_button.isEnabled()
    assert dock.aoi_text.text() == "No area selected"


def test_results_timeline_assets_and_thumbnail_layout(dock, results_page, qgis_app):
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
    qgis_app.processEvents()
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


def test_pagination_preserves_total_and_recovers_from_failure(dock, results_page, pending):
    first, new = results_page
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
    dock.next_page()
    pending.pop()[2]("Service unavailable")
    assert dock.page_index == 0
    assert len(dock.items) == 3
    assert dock.pagination_error.text() == "Could not load page 2: Service unavailable"
    dock.client = None


def test_quotes_are_per_card_and_cancelled_purchase_sends_nothing(dock, commercial, pending):
    dock.page_index = 0
    dock.display_page(
        {"features": [commercial, dict(commercial, id="two")], "numberMatched": None, "numMatched": None}
    )
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


def test_workspace_filter_preserves_asset_selection_and_expansion(dock, commercial):
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


def test_stream_failure_automatically_downloads_without_prompt(dock, commercial, pending):
    dock.display_page({"features": [commercial]})
    dock.client = Mock(base="https://example.test")
    card = dock.result_cards[0]
    card.assets.boxes[0][0].setChecked(True)
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "fallback fixture", "memory")
    task = Mock()
    task.isCanceled.return_value = False
    with (
        patch(
            "eodh_qgis.raster_loader.load_asset",
            side_effect=[StreamingUnavailable("No range support"), ([layer], False)],
        ) as loader,
        patch.object(
            QtWidgets.QMessageBox, "question", side_effect=AssertionError("Download must not ask permission")
        ),
    ):
        dock.load_card(card)
        work, done, _ = pending.pop()
        done(work(task))
        assert card.loading
        assert len(pending) == 1
        work, done, _ = pending.pop()
        done(work(task))
        assert [call.kwargs["download"] for call in loader.call_args_list] == [False, True]
        assert any("Downloading full file" in call.args[0] for call in task.asset_stage.emit.call_args_list)
        assert not card.loading
        assert QgsProject.instance().mapLayer(layer.id()) is layer
        assert dock.status.text() == "Asset loaded"
    QgsProject.instance().removeMapLayer(layer.id())
    dock.client = None


def test_projected_multilayer_aoi_import_transforms_bounds(dock, tmp_path):
    vector = QgsVectorLayer("Polygon?crs=EPSG:3857", "AOI", "memory")
    feature = QgsFeature()
    feature.setGeometry(
        QgsGeometry.fromWkt("POLYGON((0 0,111319.490793 0,111319.490793 111325.142866,0 111325.142866,0 0))")
    )
    vector.dataProvider().addFeatures([feature])
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    path = str(tmp_path / "area.gpkg")
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
