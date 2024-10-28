import unittest
from unittest.mock import MagicMock, patch

import pyeodh.ades
from qgis.PyQt import QtWidgets

from eodh_qgis.gui.wf_executor_widget import WorkflowExecutorWidget
from eodh_qgis.test.utilities import get_qgis_app


class TestWorkflowExecutorWidget(unittest.TestCase):
    """Test suite for WorkflowExecutorWidget class."""

    @classmethod
    def setUpClass(cls):
        cls.QGIS_APP = get_qgis_app()
        assert cls.QGIS_APP is not None

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_ades = MagicMock(spec=pyeodh.ades.Ades)
        self.mock_process = MagicMock()
        self.mock_process.inputs_schema = {
            "input1": {
                "schema": {"type": "string", "default": "default_value"},
                "description": "Test input 1",
            },
            "input2": {
                "schema": {"type": "number"},
                "description": "Test input 2",
            },
        }
        self.mock_ades.get_process.return_value = self.mock_process

        # Create a proper widget hierarchy
        self.main_dialog = QtWidgets.QDialog()
        self.main_dialog.jobs_widget = MagicMock()
        self.main_dialog.jobs_button = MagicMock()
        self.main_dialog.style_menu_button = MagicMock()

        self.content_widget = QtWidgets.QStackedWidget(self.main_dialog)
        self.stacked_widget = QtWidgets.QStackedWidget(self.content_widget)
        self.placeholder_widget = QtWidgets.QWidget()  # Add a widget at index 0
        self.stacked_widget.addWidget(self.placeholder_widget)

        self.widget = WorkflowExecutorWidget(
            process_id="test_process",
            ades_svc=self.mock_ades,
            parent=self.stacked_widget,
        )
        self.stacked_widget.addWidget(self.widget)
        self.stacked_widget.setCurrentWidget(self.widget)

    def tearDown(self):
        """Clean up after each test."""
        self.widget.deleteLater()
        self.stacked_widget.deleteLater()
        self.content_widget.deleteLater()
        self.main_dialog.deleteLater()
        QtWidgets.QApplication.processEvents()

    def test_init(self):
        """Test widget initialization."""
        self.assertIsInstance(self.widget, WorkflowExecutorWidget)
        self.assertEqual(self.widget.process, self.mock_process)
        self.assertIsInstance(self.widget.input_map, dict)
        self.assertEqual(len(self.widget.input_map), 2)

    def test_create_inputs(self):
        """Test if input fields are created correctly."""
        # Check if input fields were created
        self.assertEqual(len(self.widget.input_map), 2)

        # Check if default value is set correctly
        self.assertEqual(self.widget.input_map["input1"].text(), "default_value")

        # Check if empty input has empty text
        self.assertEqual(self.widget.input_map["input2"].text(), "")

    def test_handle_cancel(self):
        """Test cancel button functionality."""
        self.widget.handle_cancel()
        # Should return to first widget in stack
        self.assertEqual(self.stacked_widget.currentIndex(), 0)

    def test_handle_execute(self):
        """Test execute button functionality."""
        # Create patch context for JobDetailsWidget
        with patch(
            "eodh_qgis.gui.wf_executor_widget.JobDetailsWidget"
        ) as mock_details_widget:
            # Create a real QWidget instance for the mock to return
            mock_details_instance = QtWidgets.QWidget()
            mock_details_widget.return_value = mock_details_instance

            # Set some input values
            self.widget.input_map["input1"].setText("test_value1")
            self.widget.input_map["input2"].setText("123")

            # Mock the job creation
            mock_job = MagicMock()
            self.mock_process.execute.return_value = mock_job

            # Execute the workflow
            self.widget.handle_execute()

            # Verify process execution was called with correct inputs
            self.mock_process.execute.assert_called_once_with(
                {"input1": "test_value1", "input2": "123"}
            )

            # Verify JobDetailsWidget was created with correct parameters
            mock_details_widget.assert_called_once_with(
                job=mock_job, parent=self.stacked_widget
            )

            # Verify jobs were reloaded
            self.main_dialog.jobs_widget.load_jobs.assert_called_once()
            self.main_dialog.style_menu_button.assert_called_once_with(
                self.main_dialog.jobs_button
            )


if __name__ == "__main__":
    unittest.main()
