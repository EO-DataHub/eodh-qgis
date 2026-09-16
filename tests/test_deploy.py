"""Verify that distributable builds contain the current UI and its documentation."""

import configparser
import os
import re
import tempfile
import unittest
from pathlib import Path

import deploy


class PackageTests(unittest.TestCase):
    def test_build_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = Path.cwd()
            try:
                os.chdir(root)
                deploy.build(build_dir=root / "plugin")
            finally:
                os.chdir(previous)
            package = root / "plugin"
            metadata = configparser.ConfigParser()
            metadata.read(package / "metadata.txt", encoding="utf-8")
            self.assertTrue((package / metadata["general"]["icon"]).is_file())
            self.assertTrue((package / "gui/hub_dock.py").is_file())
            self.assertTrue((package / "brand/calendar.svg").is_file())
            guide = (package / "USAGE_GUIDE.md").read_text(encoding="utf-8")
            for image in re.findall(r"!\[[^]]*\]\((Images/[^)]+)\)", guide):
                self.assertTrue((package / image).is_file(), image)
            for obsolete in ("test", "ui", "resources.py", "gui/main_dialog.py"):
                self.assertFalse((package / obsolete).exists(), obsolete)
            self.assertFalse(list(package.rglob("*.pyc")))
