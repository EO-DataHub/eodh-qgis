import unittest

from qgis.PyQt import QtCore
from qgis.PyQt.QtTest import QSignalSpy

from eodh_qgis.test.utilities import get_qgis_app
from eodh_qgis.worker import Worker


class TestWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.QGIS_APP = get_qgis_app()
        assert cls.QGIS_APP is not None

    def setUp(self):
        self.threadpool = QtCore.QThreadPool()

    def test_worker_success(self):
        def success_function(progress_callback):
            progress_callback.emit(50)
            return "Success"

        worker = Worker(success_function)

        # Set up signal spies
        finished_spy = QSignalSpy(worker.signals.finished)
        result_spy = QSignalSpy(worker.signals.result)
        progress_spy = QSignalSpy(worker.signals.progress)

        # Run the worker
        self.threadpool.start(worker)

        # Wait for the finished signal
        self.assertTrue(finished_spy.wait(timeout=5000))

        # Check if signals were emitted
        self.assertEqual(len(finished_spy), 1)
        self.assertEqual(len(result_spy), 1)
        self.assertEqual(len(progress_spy), 1)

        # Check the emitted values
        self.assertEqual(result_spy[0][0], "Success")
        self.assertEqual(progress_spy[0][0], 50)

    def test_worker_error(self):
        def error_function(progress_callback):
            raise ValueError("Test error")

        worker = Worker(error_function)

        # Set up signal spies
        error_spy = QSignalSpy(worker.signals.error)
        finished_spy = QSignalSpy(worker.signals.finished)

        # Run the worker
        self.threadpool.start(worker)

        # Wait for the finished signal
        self.assertTrue(finished_spy.wait(timeout=5000))

        # Check if signals were emitted
        self.assertEqual(len(error_spy), 1)
        self.assertEqual(len(finished_spy), 1)

        # Check if the error message is correct
        error_args = error_spy[0][0]
        self.assertEqual(error_args[0], ValueError)
        self.assertEqual(str(error_args[1]), "Test error")

    def test_worker_run(self):
        def test_function(progress_callback, test_arg=None):
            progress_callback.emit(25)
            return f"Result with {test_arg}"

        # Create worker with args and kwargs
        worker = Worker(test_function, test_arg="test_value")

        # Set up signal spies
        finished_spy = QSignalSpy(worker.signals.finished)
        result_spy = QSignalSpy(worker.signals.result)
        progress_spy = QSignalSpy(worker.signals.progress)

        # Directly call run method
        worker.run()

        # Check if signals were emitted
        self.assertEqual(len(finished_spy), 1)
        self.assertEqual(len(result_spy), 1)
        self.assertEqual(len(progress_spy), 1)

        # Check the emitted values
        self.assertEqual(result_spy[0][0], "Result with test_value")
        self.assertEqual(progress_spy[0][0], 25)


if __name__ == "__main__":
    unittest.main()
