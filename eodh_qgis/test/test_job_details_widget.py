import unittest
from unittest.mock import MagicMock, patch

from eodh_qgis.gui.job_details_widget import JobDetailsWidget
import pyeodh.ades


class TestJobDetailsWidget(unittest.TestCase):
    def setUp(self):
        self.mock_job = MagicMock(spec=pyeodh.ades.Job)
        self.mock_job.id = "test_job_id"
        self.mock_job.process_id = "test_process"
        self.mock_job.status = pyeodh.ades.AdesJobStatus.SUCCESSFUL.value

        # Patch QtWidgets.QWidget.__init__ to avoid creating a real widget
        with patch("PyQt5.QtWidgets.QWidget.__init__"):
            self.widget = JobDetailsWidget(self.mock_job)

    # def test_init(self):
    #     self.assertIsInstance(self.widget, JobDetailsWidget)
    #     self.assertEqual(self.widget.job, self.mock_job)

    # @patch("eodh_qgis.gui.job_details_widget.QtWidgets.QTableWidget")
    # def test_populate_table(self, mock_table):
    #     self.widget.table = mock_table
    #     self.widget.populate_table()
    #     mock_table.setColumnCount.assert_called_once_with(1)
    #     mock_table.setRowCount.assert_called_once_with(9)
    #     mock_table.setItem.assert_called_with(0, 0, unittest.mock.ANY)
    #     mock_table.show.assert_called_once()

    # def test_handle_close(self):
    #     mock_parent = MagicMock()
    #     self.widget.parent = MagicMock(return_value=mock_parent)
    #     self.widget.handle_close()
    #     mock_parent.removeWidget.assert_called_once_with(self.widget)
    #     mock_parent.setCurrentIndex.assert_called_once_with(1)

    # @patch("eodh_qgis.gui.job_details_widget.Worker")
    # def test_trigger_polling(self, mock_worker):
    #     self.widget.trigger_polling()
    #     mock_worker.assert_called_once()
    #     mock_worker_instance = mock_worker.return_value
    #     self.widget.threadpool.start.assert_called_once_with(mock_worker_instance)

    # @patch("eodh_qgis.gui.job_details_widget.QtWidgets.QTextBrowser")
    # def test_log_msg(self, mock_text_browser):
    #     self.widget.message_log = mock_text_browser
    #     self.widget.log_msg("Test message")
    #     mock_text_browser.append.assert_called_once_with("Test message")


if __name__ == "__main__":
    unittest.main()
