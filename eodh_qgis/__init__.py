import sys


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load EodhQgis class from file EodhQgis.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """

    # truststore supports Python 3.10+; older QGIS runtimes use standard SSL.
    if sys.version_info >= (3, 10):
        try:
            import truststore

            truststore.inject_into_ssl()
        except Exception:
            pass

    from .main import EodhQgis

    return EodhQgis(iface)
