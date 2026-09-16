"""Run the current plugin tests in isolated QGIS Python processes.

Use a QGIS Python launcher, or the system Python inside an official QGIS image.
The optional coverage report includes both transport and real Qt/GDAL checks.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ("plugin", "runtime", "login", "search", "screen", "streaming", "netcdf")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", action="store_true", help="Write coverage.xml for the current plugin.")
    args = parser.parse_args()
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")

    def run(arguments):
        subprocess.run([sys.executable, *arguments], cwd=ROOT, env=env, check=True, timeout=180)

    prefix = ["-m", "coverage", "run", "--parallel-mode"] if args.coverage else []
    if args.coverage:
        run(["-m", "coverage", "erase"])
    run([*prefix, "-m", "unittest", "discover", "-s", "tests", "-v"])
    for check in CHECKS:
        print(f"Running QGIS {check} checks", flush=True)
        run([*prefix, str(ROOT / "tests" / f"qgis_{check}_check.py")])
    if args.coverage:
        run(["-m", "coverage", "combine"])
        run(["-m", "coverage", "xml"])
        run(["-m", "coverage", "report"])


if __name__ == "__main__":
    main()
