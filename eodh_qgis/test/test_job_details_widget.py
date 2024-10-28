import unittest
from unittest.mock import MagicMock, patch

from eodh_qgis.gui.job_details_widget import JobDetailsWidget
from eodh_qgis.test.utilities import get_qgis_app


class TestJobDetailsWidget(unittest.TestCase):
    """Test suite for JobDetailsWidget class.

    This class contains basic unit tests for the JobDetailsWidget functionality,
    focusing on initialization and simple interactions.
    """

    @classmethod
    def setUpClass(cls):
        cls.QGIS_APP = get_qgis_app()
        assert cls.QGIS_APP is not None

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.mock_job = MagicMock()
        self.mock_job.id = "test_job_id"
        self.mock_job.process_id = "test_process"
        self.mock_job.type = "test_type"
        self.mock_job.status = "successful"
        self.mock_job.progress = 100
        self.mock_job.created = "2024-01-01"
        self.mock_job.started = "2024-01-01"
        self.mock_job.finished = "2024-01-01"
        self.mock_job.updated = "2024-01-01"

        self.widget = JobDetailsWidget(self.mock_job)

    def tearDown(self) -> None:
        """Runs after each test."""
        self.widget = None

    def test_init(self) -> None:
        """Test widget initialization."""
        self.assertEqual(self.widget.job, self.mock_job)
        self.assertEqual(self.widget.outputs, [])
        self.assertEqual(len(self.widget.logs), 0)

    def test_populate_table(self) -> None:
        """Test if the table is populated correctly with job details."""
        # Check if table has correct number of rows (9 job attributes)
        self.assertEqual(self.widget.table.rowCount(), 9)

        # Check if some key values are correctly displayed
        self.assertEqual(self.widget.table.item(0, 0).text(), "test_job_id")

    @patch("eodh_qgis.gui.job_details_widget.Worker")
    def test_message_polling(self, mock_worker):
        mock_worker_instance = MagicMock()
        mock_worker.return_value = mock_worker_instance

        # Mock the threadpool to avoid actually starting the worker
        with patch.object(self.widget.threadpool, "start") as mock_start:
            self.widget.trigger_polling()

            self.assertTrue(mock_worker.called)
            self.assertTrue(mock_worker_instance.signals.progress.connect.called)
            self.assertTrue(mock_worker_instance.signals.finished.connect.called)
            self.assertTrue(mock_start.called)

    def test_log_msg(self) -> None:
        """Test if messages are logged correctly."""
        test_message = "Test message"
        initial_text = self.widget.message_log.toPlainText()

        self.widget.log_msg(test_message)

        # Verify message appears in the log
        self.assertIn(test_message, self.widget.message_log.toPlainText())
        self.assertNotEqual(initial_text, self.widget.message_log.toPlainText())

    def test_handle_close(self) -> None:
        """Test close button functionality."""
        mock_parent = MagicMock()
        self.widget.parent = MagicMock(return_value=mock_parent)

        self.widget.handle_close()

        # Verify that removeWidget was called
        mock_parent.removeWidget.assert_called_once_with(self.widget)
        mock_parent.setCurrentIndex.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
