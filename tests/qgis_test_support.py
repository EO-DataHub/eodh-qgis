"""Exit isolated QGIS tests after saving coverage and output."""

import os
import sys


def finish(code=0):
    # QGIS/Qt global destruction order can crash Python during finalization.
    # Save tracing data before bypassing native interpreter teardown.
    coverage_module = sys.modules.get("coverage")
    if coverage_module:
        active = coverage_module.Coverage.current()
        if active:
            active.stop()
            active.save()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
