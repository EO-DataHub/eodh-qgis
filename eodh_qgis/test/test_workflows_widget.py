import unittest
from unittest.mock import MagicMock, patch
from PyQt5 import QtWidgets

from eodh_qgis.gui.workflows_widget import WorkflowsWidget


class TestWorkflowsWidget(unittest.TestCase):

    def setUp(self):
        self.ades_svc = MagicMock()
        self.widget = WorkflowsWidget(self.ades_svc)

    def tearDown(self):
        self.widget.deleteLater()

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
