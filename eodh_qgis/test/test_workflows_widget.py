import unittest
from unittest.mock import MagicMock, patch

from qgis.PyQt import QtWidgets

from eodh_qgis.gui.workflows_widget import WorkflowsWidget
from eodh_qgis.test.utilities import get_qgis_app


class TestWorkflowsWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.QGIS_APP = get_qgis_app()
        assert cls.QGIS_APP is not None

    def setUp(self):
        """Create fresh instances for each test"""
        self.ades_svc = MagicMock()
        self.main_dialog = QtWidgets.QDialog()
        self.widget = WorkflowsWidget(self.ades_svc, parent=self.main_dialog)

    def tearDown(self):
        """Clean up widgets after each test"""
        self.widget.deleteLater()
        self.main_dialog.deleteLater()
        # Process any pending events before moving to next test
        QtWidgets.QApplication.instance().processEvents()

    def test_init(self):
        self.assertIsInstance(self.widget, WorkflowsWidget)
        self.assertEqual(self.widget.ades_svc, self.ades_svc)
        self.assertFalse(self.widget.row_selected)

    def test_handle_table_click(self):
        self.widget.handle_table_click(0, 0)
        self.assertTrue(self.widget.row_selected)
        self.assertTrue(self.widget.execute_button.isEnabled())
        self.assertTrue(self.widget.edit_button.isEnabled())
        self.assertTrue(self.widget.remove_button.isEnabled())

    @patch("eodh_qgis.gui.workflows_widget.Worker")
    def test_load_workflows(self, mock_worker):
        mock_worker_instance = MagicMock()
        mock_worker.return_value = mock_worker_instance

        # Mock the threadpool to avoid actually starting the worker
        with patch.object(self.widget.threadpool, "start") as mock_start:
            self.widget.load_workflows()

            self.assertTrue(mock_worker.called)
            self.assertTrue(mock_worker_instance.signals.result.connect.called)
            self.assertTrue(mock_worker_instance.signals.finished.connect.called)
            self.assertTrue(mock_start.called)

        # Simulate the worker finishing
        mock_worker_instance.signals.finished.emit()
        self.assertFalse(self.widget.new_button.isEnabled())

    def test_lock_form(self):
        self.widget.lock_form(True)
        self.assertFalse(self.widget.new_button.isEnabled())
        self.assertFalse(self.widget.edit_button.isEnabled())
        self.assertFalse(self.widget.execute_button.isEnabled())
        self.assertFalse(self.widget.remove_button.isEnabled())
        self.assertFalse(self.widget.table.isEnabled())

        self.widget.lock_form(False)
        self.assertTrue(self.widget.new_button.isEnabled())
        self.assertFalse(self.widget.edit_button.isEnabled())
        self.assertFalse(self.widget.execute_button.isEnabled())
        self.assertFalse(self.widget.remove_button.isEnabled())
        self.assertTrue(self.widget.table.isEnabled())


if __name__ == "__main__":
    unittest.main()
