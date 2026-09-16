"""Exercise real task callbacks and UI recovery with a deterministic task queue."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qgis.core import QgsApplication
from qgis.gui import QgsMapCanvas
from qgis.PyQt import QtCore, QtWidgets
from qgis_test_support import finish

from eodh_qgis.api.hub import HubError
from eodh_qgis.gui.hub_dock import HubDock

app = QgsApplication([], False)
app.initQgis()
window = QtWidgets.QMainWindow()
canvas = QgsMapCanvas(window)
iface = Mock()
iface.mainWindow.return_value = window
iface.mapCanvas.return_value = canvas
with patch.object(HubDock, "load_credentials", lambda self: None):
    dock = HubDock(iface)
window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
dock.stack.setCurrentWidget(dock.tabs)
window.show()
app.processEvents()
client = Mock()
dock.client = client
queued = []
manager = Mock()
manager.addTask.side_effect = queued.append


def complete(task=None):
    task = queued.pop(0) if task is None else task
    success = task.run()
    task.finished(success)
    assert task.work is None
    assert task.finish_callback is None
    return task


# Keep the real HubTask and submit/finish logic; only control when tasks run.
with patch("eodh_qgis.gui.hub_dock.QgsApplication.taskManager", return_value=manager):
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

    # Cancellation never invokes the work, and returns a recoverable error.
    work, done, failed = Mock(), Mock(), Mock()
    dock.submit("Cancel me", work, done, failed)
    queued[0].cancel()
    complete()
    work.assert_not_called()
    done.assert_not_called()
    assert str(failed.call_args.args[0]) == "Operation cancelled."
    assert dock.progress.isHidden()

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

    # Commercial controls use asynchronous responses and enforce a fresh quote.
    item_url = "https://eodatahub.org.uk/catalogs/commercial/catalogs/airbus/items/scene"
    item = {"id": "scene", "collection": "airbus-optical", "links": [{"rel": "self", "href": item_url}]}
    dock.display_page({"features": [item]})
    while queued:
        complete()
    panel = dock.result_cards[0].commercial
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

    client.request.return_value = {"value": "invalid", "units": "GBP"}
    panel.quote_button.click()
    complete()
    assert panel.purchase_error.text() == "EODH returned an invalid quote. Retry."
    assert not panel.order_button.isEnabled()
    client.request.side_effect = HubError("Provider unavailable", 503)
    panel.quote_button.click()
    complete()
    assert panel.purchase_error.text() == "Provider unavailable"
    assert panel.quote_button.isEnabled()
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

dock.shutdown()
print(
    "PASS task progress/cancellation/session isolation, workspace refresh/filter/retry, quote/order responses and authentication expiry"
)
finish()
