from unittest.mock import Mock

import pytest
from qgis.PyQt import QtCore


@pytest.fixture
def search_form(dock, pending, collection_entry):
    client = Mock()
    dock.client = client
    client.discover.return_value = [collection_entry]
    client.cloud_supported.return_value = True
    dock.discover()
    work, done, _ = pending.pop()
    done(work())
    work, done, _ = pending.pop()
    done(work())
    dock.start.setDate(QtCore.QDate(2026, 1, 1))
    dock.end.setDate(QtCore.QDate(2026, 2, 1))
    client.request.return_value = {"features": [], "numberMatched": 0}
    return client


def test_catalogue_switch_ignores_stale_discovery(dock, pending, collection_entry):
    client = Mock()
    dock.client = client
    entry = collection_entry
    # Switching catalogue ignores the previous discovery's delayed response.
    dock.discover()
    public = pending.pop()
    assert not dock.collection_progress.isHidden()
    assert not dock.search_button.isEnabled()
    dock.catalogue.setCurrentText("Commercial")
    commercial = pending.pop()
    assert not dock.commercial_help.isHidden()
    public[1]([entry])
    assert dock.collection.count() == 0
    commercial[1]([])
    assert dock.search_summary.text() == "No collections are available under Commercial."
    dock.catalogue.setCurrentText("Public")
    client.discover.return_value = [entry]
    work, done, _ = pending.pop()
    done(work())
    client.discover.assert_called_once_with("Public")
    assert dock.collection.currentText() == "Sentinel 2 ARD"
    assert dock.collection_progress.isHidden()
    assert dock.commercial_help.isHidden()
    assert dock.search_button.isEnabled()
    client.cloud_supported.return_value = True
    work, done, _ = pending.pop()
    done(work())
    assert not dock.cloud_group.isHidden()


def test_search_sends_date_cloud_and_aoi_filters_and_shows_empty_results(dock, pending, search_form):
    client = search_form
    dock.start.setDate(QtCore.QDate(2026, 1, 1))
    dock.end.setDate(QtCore.QDate(2026, 2, 1))
    dock.cloud.setValue(25)
    assert dock.cloud_text.text() == "25%"
    dock.set_bbox([0.1, 0.2, 0.8, 0.9])
    dock.search_button.click()
    assert not dock.search_button.isEnabled()
    assert not dock.search_progress.isHidden()

    work, done, _ = pending.pop()
    done(work())
    client.request.assert_called_once_with(
        "https://example.test/search",
        "POST",
        {
            "collections": ["sentinel2_ard"],
            "limit": 50,
            "datetime": "2026-01-01T00:00:00Z/2026-02-01T23:59:59Z",
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "filter-lang": "cql2-json",
            "filter": {"op": "<=", "args": [{"property": "properties.eo:cloud_cover"}, 25]},
        },
    )
    assert dock.tabs.currentIndex() == 1
    assert dock.results_empty.isVisible()
    assert dock.search_summary.text() == "Found 0 items (0 shown)."
    assert dock.search_progress.isHidden()


def test_invalid_dates_block_search_and_failed_requests_allow_retry(dock, pending, search_form):
    # Invalid dates are caught before scheduling work; failures allow retry.
    dock.start.setDate(QtCore.QDate(2026, 3, 1))
    dock.search_button.click()
    assert not pending
    assert "start date must be on or before" in dock.search_summary.text()
    dock.start.setDate(QtCore.QDate(2026, 1, 1))
    dock.search_button.click()
    pending.pop()[2]("Service unavailable")
    assert dock.search_button.isEnabled()
    assert dock.search_progress.isHidden()
    assert dock.search_summary.text() == "Search failed: Service unavailable"


def test_unsupported_cloud_filter_is_omitted_and_clear_aoi_disables_search(dock, pending, search_form):
    client = search_form
    # Unsupported cloud metadata hides the control and omits its filter.
    dock.collection_changed()
    pending.pop()[1](False)
    assert dock.cloud_group.isHidden()
    dock.cloud.setValue(10)
    dock.search_button.click()
    work, done, _ = pending.pop()
    done(work())
    assert "filter" not in client.request.call_args.args[2]
    dock.clear_aoi_button.click()
    assert not dock.search_button.isEnabled()
