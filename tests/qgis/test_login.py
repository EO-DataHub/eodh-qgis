from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from qgis.PyQt import QtWidgets

from eodh_qgis.api.hub import ENVIRONMENTS, HubError
from eodh_qgis.gui.hub_dock import HubDock


@pytest.fixture
def login_service():
    values = {"eodh/hub_environment": "Staging"}
    settings = Mock()
    settings.value.side_effect = lambda key, default=None: values.get(key, default)
    settings.setValue.side_effect = values.__setitem__
    settings.remove.side_effect = lambda key: values.pop(key, None)
    manager = Mock()
    stored_config = {}

    def store_config(config):
        config.setId("test-id")
        stored_config["token"] = config.config("token")
        return True

    def load_config(auth_id, config, full):
        assert auth_id == "test-id"
        assert full
        config.setConfig("token", stored_config["token"])
        return True

    def submit(self, title, work, done, failed=None):
        try:
            result = work()
        except HubError as error:
            failed(error)
        else:
            done(result)

    manager.storeAuthenticationConfig.side_effect = store_config
    manager.loadAuthenticationConfig.side_effect = load_config
    client = Mock()
    client.validate.return_value = {}
    with (
        patch("eodh_qgis.gui.hub_dock.QtCore.QSettings", return_value=settings),
        patch("eodh_qgis.gui.hub_dock.QgsApplication") as application,
        patch("eodh_qgis.gui.hub_dock.HubClient", return_value=client) as client_type,
        patch.object(HubDock, "submit", submit),
        patch.object(HubDock, "discover"),
        patch.object(HubDock, "refresh_records"),
    ):
        application.authManager.return_value = manager
        yield SimpleNamespace(values=values, manager=manager, client=client, client_type=client_type)


@pytest.fixture
def signed_in(login_service, dock_factory):
    dock = dock_factory(restore=True)
    dock.workspace.setText("workspace")
    dock.key.setText("fake-test-key")
    dock.connect_workspace()
    return login_service


def test_login_layout_validation_and_encrypted_save(login_service, dock_factory, qgis_app):
    values, manager, _client, client_type = (
        login_service.values,
        login_service.manager,
        login_service.client,
        login_service.client_type,
    )
    dock = dock_factory(restore=True)
    dock.resize(370, 300)
    dock.login_scroll.setFixedHeight(200)
    dock.show()
    qgis_app.processEvents()
    assert dock.workspace.height() >= 22
    assert dock.key.height() >= 24
    assert dock.login_scroll.verticalScrollBar().maximum() > 0
    dock.login_scroll.setMinimumHeight(0)
    dock.login_scroll.setMaximumHeight(16777215)
    assert dock.header.isHidden()
    assert dock.status.isHidden()
    assert not dock.login.findChildren(QtWidgets.QComboBox)
    assert not dock.login.findChildren(QtWidgets.QCheckBox)
    assert not dock.connect_button.isEnabled()
    dock.workspace.setText(" workspace & example ")
    assert "workspace%20%26%20example" in dock.login.credentials.text()
    assert dock.connect_button.isEnabled()
    dock.connect_workspace()
    assert dock.login.error.text() == "Please enter your workspace API key (not the Token ID)."
    assert not client_type.called
    dock.workspace.setText("workspace")
    dock.key.setText("fake-test-key")
    dock.connect_workspace()
    client_type.assert_called_once_with(ENVIRONMENTS["Production"], "workspace", "fake-test-key")
    manager.storeAuthenticationConfig.assert_called_once()
    assert values["eodh/hub_auth"] == "test-id"
    assert "fake-test-key" not in str(values)
    assert dock.key.text() == ""
    assert dock.stack.currentWidget() is dock.tabs
    assert not dock.header.isHidden()


def test_saved_credentials_restore_automatically(signed_in, dock_factory, qgis_app):
    restored = dock_factory(restore=True)
    qgis_app.processEvents()
    assert restored.client is signed_in.client
    signed_in.manager.loadAuthenticationConfig.assert_called_once()
    assert signed_in.manager.storeAuthenticationConfig.call_count == 1


def test_expired_credentials_return_to_login_and_clear_storage(signed_in, dock_factory, qgis_app):
    client, values, manager = signed_in.client, signed_in.values, signed_in.manager
    client.validate.side_effect = HubError("Expired key", 401)
    expired = dock_factory(restore=True)
    qgis_app.processEvents()
    assert expired.client is None
    assert expired.stack.currentWidget() is expired.login_scroll
    assert expired.login.error.text() == "Expired key"
    assert expired.key.text() == ""
    assert "eodh/hub_auth" not in values
    manager.removeAuthenticationConfig.assert_called_with("test-id")


def test_sign_out_clears_credentials(signed_in, dock_factory):
    client, values = signed_in.client, signed_in.values
    client.validate.side_effect = None
    final = dock_factory(restore=True)
    final.key.setText("fake-test-key")
    final.connect_workspace()
    final.disconnect()
    assert final.client is None
    assert final.header.isHidden()
    assert "eodh/hub_auth" not in values
    assert final.key.text() == ""
