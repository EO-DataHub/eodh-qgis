"""Verify that distributable builds contain the current UI and its documentation."""

import configparser
import re

import deploy


def test_build_from_another_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    deploy.build(build_dir=tmp_path / "plugin")
    package = tmp_path / "plugin"
    metadata = configparser.ConfigParser()
    metadata.read(package / "metadata.txt", encoding="utf-8")
    assert (package / metadata["general"]["icon"]).is_file()
    assert (package / "gui/hub_dock.py").is_file()
    assert (package / "brand/calendar.svg").is_file()
    guide = (package / "USAGE_GUIDE.md").read_text(encoding="utf-8")
    for image in re.findall("!\\[[^]]*\\]\\((Images/[^)]+)\\)", guide):
        assert (package / image).is_file(), image
    for obsolete in ("test", "ui", "resources.py", "gui/main_dialog.py"):
        assert not (package / obsolete).exists(), obsolete
    assert not list(package.rglob("*.pyc"))
