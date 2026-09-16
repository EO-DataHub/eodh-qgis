# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load EodhQgis class from file EodhQgis.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """

    from .main import EodhQgis

    return EodhQgis(iface)
