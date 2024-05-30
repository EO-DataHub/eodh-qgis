import os
import platform
import site


def include_deps():
    system = platform.system()
    if system not in ["Linux", "Darwin", "Windows"]:
        return

    deps_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), f"libs/{system.lower()}")
    )
    site.addsitedir(deps_path)


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load EodhQgis class from file EodhQgis.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """

    include_deps()

    from .main import EodhQgis

    return EodhQgis(iface)
