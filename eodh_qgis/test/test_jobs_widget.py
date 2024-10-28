import unittest
from unittest.mock import MagicMock

import pyeodh.ades
from qgis.PyQt import QtWidgets

from eodh_qgis.gui.jobs_widget import JobsWidget
from eodh_qgis.test.utilities import get_qgis_app


class TestJobsWidget(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.QGIS_APP = get_qgis_app()
        assert cls.QGIS_APP is not None

    def setUp(self):
        self.ades_svc = MagicMock(spec=pyeodh.ades.Ades)
        self.parent = QtWidgets.QWidget()
        self.jobs_widget = JobsWidget(self.ades_svc, parent=self.parent)

    def tearDown(self):
        """Runs after each test."""
        self.jobs_widget = None

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
