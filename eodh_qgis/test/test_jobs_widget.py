import unittest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt

from eodh_qgis.gui.jobs_widget import JobsWidget
import pyeodh.ades


class TestJobsWidget(unittest.TestCase):

    def setUp(self):
        self.ades_svc = MagicMock(spec=pyeodh.ades.Ades)
        self.parent = QWidget()
        self.jobs_widget = JobsWidget(self.ades_svc, parent=self.parent)

    def test_init(self):
        self.assertIsInstance(self.jobs_widget, JobsWidget)
        self.assertEqual(self.jobs_widget.ades_svc, self.ades_svc)
        self.assertEqual(len(self.jobs_widget.jobs), 0)
        self.assertFalse(self.jobs_widget.row_selected)

    def test_handle_table_click(self):
        self.jobs_widget.handle_table_click(0, 0)
        self.assertTrue(self.jobs_widget.row_selected)
        self.assertTrue(self.jobs_widget.details_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
