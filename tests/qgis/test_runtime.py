import pytest
from qgis.core import QgsProject


@pytest.fixture
def result(dock, qgis_app):
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
    qgis_app.processEvents()
    return item


def test_tabs_and_catalogue_roots(dock):
    assert [dock.tabs.tabText(i) for i in range(dock.tabs.count())] == ["Search", "Results", "Workspace"]
    assert [dock.catalogue.itemText(i) for i in range(dock.catalogue.count())] == ["Public", "Commercial"]


def test_map_footprints_follow_visibility_and_clear(dock, result):
    assert len(dock.overlays.bands) == 1
    assert len(QgsProject.instance().mapLayers()) == 0
    assert dock.results.currentRow() == dock.timeline.index == 0
    dock.show_footprints.setChecked(False)
    assert not dock.overlays.bands
    dock.show_footprints.setChecked(True)
    assert len(dock.overlays.bands) == 1
    dock.clear_results()
    assert not dock.overlays.bands


def test_quote_is_invalidated_by_input_aoi_or_item_changes(dock, result, monkeypatch):
    item = result
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
    dock.client = object()
    monkeypatch.setattr(dock, "submit", lambda title, work, done, failed=None, **kwargs: callbacks.append(done))
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


@pytest.mark.parametrize(("status", "enabled"), [("pending", False), ("failed", False), ("completed", True)])
def test_workspace_only_loads_completed_records(dock, result, status, enabled):
    record = dict(result, _provider="Airbus", properties={"order:status": status})
    dock.records = [record]
    dock.filter_records()
    assert dock.record_cards[0].load_button.isEnabled() == enabled
