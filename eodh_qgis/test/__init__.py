# import qgis libs so that ve set the correct sip api version
import qgis  # pylint: disable=W0611  # NOQA

import os
import sys
import qgis.core

# Initialize QGIS Application
qgs = qgis.core.QgsApplication([], False)
qgs.initQgis()

# Add the path to your plugin
plugin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(plugin_path)
