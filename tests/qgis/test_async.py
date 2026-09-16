from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from qgis.PyQt import QtWidgets

from eodh_qgis.api.hub import HubError


@pytest.fixture
def task_queue(dock, monkeypatch):
    queued = []
    client = Mock()
    dock.client = client
    manager = Mock()
    manager.addTask.side_effect = queued.append
    monkeypatch.setattr("eodh_qgis.gui.hub_dock.QgsApplication.taskManager", lambda: manager)

    def complete(task=None):
        task = queued.pop(0) if task is None else task
        success = task.run()
        task.finished(success)
        assert task.work is None
        assert task.finish_callback is None
        return task

    yield SimpleNamespace(queued=queued, client=client, complete=complete)
    for task in list(queued):
        task.cancel()
        complete()


def test_download_progress(dock, task_queue):
    queued, _client, complete = task_queue.queued, task_queue.client, task_queue.complete
    done, failed = Mock(), Mock()
    dock.submit("Download", lambda task: "loaded", done, failed, with_task=True)
    task = queued[0]
    assert not dock.progress.isHidden()
    task.asset_stage.emit("Streaming raster")
    assert dock.status_detail.text() == "Streaming raster"
    task.download_progress.emit("raster", 1048576, 2097152)
    assert dock.status_percent.text() == "50%"
    assert dock.progress.value() == 50
    task.download_progress.emit("raster", 1048576, 0)
    assert dock.status_percent.text() == ""
    complete()
    done.assert_called_once_with("loaded")
    failed.assert_not_called()
    assert not dock.tasks
    assert dock.status.text() == "Ready"
    assert dock.progress.isHidden()


def test_cancelled_work(dock, task_queue):
    queued, _client, complete = task_queue.queued, task_queue.client, task_queue.complete
    # Cancellation never invokes the work, and returns a recoverable error.
    work, done, failed = Mock(), Mock(), Mock()
    dock.submit("Cancel me", work, done, failed)
    queued[0].cancel()
    complete()
    work.assert_not_called()
    done.assert_not_called()
    assert str(failed.call_args.args[0]) == "Operation cancelled."
    assert dock.progress.isHidden()


def test_stale_session_callbacks(dock, task_queue):
    queued, _client, complete = task_queue.queued, task_queue.client, task_queue.complete
    # Responses and progress from a previous session cannot mutate the current UI.
    done = Mock()
    dock.submit("Old request", lambda task: "old", done, with_task=True)
    dock.epoch += 1
    dock.status_detail.setText("Current session")
    queued[0].asset_stage.emit("Stale stage")
    queued[0].download_progress.emit("old", 1, 2)
    complete()
    done.assert_not_called()
    assert dock.status_detail.text() == "Current session"
    assert not dock.tasks


def test_workspace_retry_and_filters(dock, task_queue):
    _queued, client, complete = task_queue.queued, task_queue.client, task_queue.complete
    # Refresh errors expose Retry; successful refresh populates both filters.
    dock.tabs.setCurrentIndex(2)
    client.records.side_effect = HubError("Service temporarily unavailable", 503)
    dock.refresh_button.click()
    assert not dock.refresh_button.isEnabled()
    assert not dock.workspace_progress.isHidden()
    complete()
    assert dock.refresh_button.isEnabled()
    assert dock.workspace_error.text() == "Service temporarily unavailable"
    assert not dock.workspace_retry.isHidden()
    client.records.side_effect = None
    client.records.return_value = [
        {"id": "delivered", "_provider": "Airbus", "properties": {"order:status": "succeeded"}},
        {"id": "pending", "_provider": "Planet", "properties": {"order:status": "pending"}},
    ]
    dock.workspace_retry.click()
    complete()
    assert dock.workspace_error.isHidden()
    assert dock.workspace_retry.isHidden()
    assert len(dock.record_cards) == 2
    assert [dock.provider_filter.itemText(i) for i in range(dock.provider_filter.count())] == [
        "All",
        "Airbus",
        "Planet",
    ]
    dock.provider_filter.setCurrentText("Planet")
    assert [card.item["id"] for card in dock.record_cards] == ["pending"]
    dock.status_filter.setCurrentText("succeeded")
    assert not dock.record_cards
    assert not dock.workspace_empty.isHidden()
    dock.provider_filter.setCurrentText("All")
    assert [card.item["id"] for card in dock.record_cards] == ["delivered"]


def test_workspace_ignores_stale_refresh_error(dock, task_queue):
    queued, client, complete = task_queue.queued, task_queue.client, task_queue.complete
    client.records.return_value = [{"id": "one", "_provider": "Airbus"}, {"id": "two", "_provider": "Planet"}]
    # Only the latest refresh may populate records, including after an older error.
    dock.refresh_records()
    old = queued.pop()
    dock.refresh_records()
    complete()
    client.records.side_effect = HubError("Obsolete refresh", 503)
    complete(old)
    assert dock.workspace_error.isHidden()
    assert len(dock.records) == 2
    client.records.side_effect = None


@pytest.fixture
def commercial_panel(dock, task_queue):
    queued, _client, complete = task_queue.queued, task_queue.client, task_queue.complete
    # Commercial controls use asynchronous responses and enforce a fresh quote.
    item_url = "https://eodatahub.org.uk/catalogs/commercial/catalogs/airbus/items/scene"
    item = {"id": "scene", "collection": "airbus-optical", "links": [{"rel": "self", "href": item_url}]}
    dock.display_page({"features": [item]})
    while queued:
        complete()
    panel = dock.result_cards[0].commercial
    return panel


def test_successful_quote_and_order(commercial_panel, task_queue):
    panel = commercial_panel
    client, complete = task_queue.client, task_queue.complete
    item_url = "https://eodatahub.org.uk/catalogs/commercial/catalogs/airbus/items/scene"
    client.request.return_value = {"value": 12.5, "units": "GBP"}
    panel.quote_button.click()
    assert panel.busy
    assert not panel.quote_button.isEnabled()
    complete()
    assert panel.quote_text.text() == "12.50 GBP"
    assert panel.order_button.isEnabled()
    assert client.request.call_args.args[0] == item_url + "/quote"
    # Every purchase response is mocked: no order is sent to EODH.
    with patch.object(QtWidgets.QMessageBox, "warning", return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        panel.order_button.click()
    assert not panel.order_button.isEnabled()
    complete()
    assert client.request.call_args.args[0:2] == (item_url + "/order", "POST")
    assert client.request.call_args.args[2]["endUserCountry"] == "GB"
    assert client.request.call_args.kwargs == {"raw": True}
    assert panel.purchase_status.text() == "Ordered — check workspace for delivery status"
    assert not panel.order_button.isEnabled()


def test_invalid_quote_disables_order(commercial_panel, task_queue):
    panel = commercial_panel
    client, complete = task_queue.client, task_queue.complete
    client.request.return_value = {"value": "invalid", "units": "GBP"}
    panel.quote_button.click()
    complete()
    assert panel.purchase_error.text() == "EODH returned an invalid quote. Retry."
    assert not panel.order_button.isEnabled()


def test_quote_failure_allows_retry(commercial_panel, task_queue):
    panel = commercial_panel
    client, complete = task_queue.client, task_queue.complete
    client.request.side_effect = HubError("Provider unavailable", 503)
    panel.quote_button.click()
    complete()
    assert panel.purchase_error.text() == "Provider unavailable"
    assert panel.quote_button.isEnabled()


def test_order_failure_requires_fresh_quote(commercial_panel, task_queue):
    panel = commercial_panel
    client, complete = task_queue.client, task_queue.complete
    client.request.side_effect = None
    client.request.return_value = {"value": 12.5, "units": "GBP"}
    panel.quote_button.click()
    complete()
    client.request.side_effect = HubError("Order rejected", 409)
    with patch.object(QtWidgets.QMessageBox, "warning", return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        panel.order_button.click()
    complete()
    assert panel.purchase_error.text() == "Order rejected"
    assert not panel.order_button.isEnabled()
    assert panel.quote_button.isEnabled()


def test_session_expiry(dock, task_queue):
    queued, _client, complete = task_queue.queued, task_queue.client, task_queue.complete
    # Authentication expiry returns to login and cancels other outstanding work.
    done, failed = Mock(), Mock()
    dock.submit("Outstanding", lambda: None, Mock())
    outstanding = queued.pop()
    dock.submit("Expired", Mock(side_effect=HubError("Session expired", 401)), done, failed)
    with patch.object(dock, "clear_saved_credentials"):
        complete()
    assert dock.client is None
    assert dock.stack.currentWidget() is dock.login_scroll
    assert dock.login.error.text() == "Session expired"
    assert outstanding.isCanceled()
    done.assert_not_called()
    failed.assert_called_once()
    complete(outstanding)
