import sys
from qgis.testing import unittest
import qgis  # NOQA  For SIP API to V2 if run outside of QGIS

import coverage

from qgis.PyQt import Qt

from qgis.core import Qgis


def _run_tests(test_suite, package_name):
    """Core function to test a test suite."""
    count = test_suite.countTestCases()

    version = str(Qgis.QGIS_VERSION_INT)
    version = int(version)

    print("########")
    print("%s tests has been discovered in %s" % (count, package_name))
    print("QGIS : %s" % version)
    print("QT : %s" % Qt.QT_VERSION_STR)
    print("########")
    cov = coverage.Coverage(
        source=["./"],
        omit=["*/test/*"],
    )
    cov.start()

    unittest.TextTestRunner(verbosity=3, stream=sys.stdout).run(test_suite)

    cov.stop()
    cov.save()
    cov.xml_report()


def test_package(package="test"):
    """Test package.
    This function is called by Github actions or travis without arguments.
    :param package: The package to test.
    :type package: str
    """
    test_loader = unittest.defaultTestLoader
    try:
        test_suite = test_loader.discover(package)
    except ImportError:
        test_suite = unittest.TestSuite()
    _run_tests(test_suite, package)
