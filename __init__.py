# -*- coding: utf-8 -*-
"""
/***************************************************************************
 EodhQgis
                                 A QGIS plugin
 Access and run workflows on the EODH
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2024-04-09
        copyright            : (C) 2024 by Oxidian
        email                : daniel@oxidian.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


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

    from .eodh_qgis import EodhQgis

    return EodhQgis(iface)
