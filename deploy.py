#!/bin/python3

import argparse
import os
import pathlib
import shutil
import sys
import subprocess

ROOT_DIR = pathlib.Path(__file__).parent.resolve()
BUILD_DIR = ROOT_DIR / "build"
SRC_DIR = ROOT_DIR / "eodh_qgis"
RESOURCE_PATH = ROOT_DIR / "resources/resources.qrc"
LIBS_DIR = ROOT_DIR / "libs"


def main(install_path: pathlib.Path):
    if not install_path:
        print("Provide qgis plugin path")
        sys.exit(1)
    verify_install_path(install_path)
    uninstall(install_path)
    build()
    compile_resources()
    patch_resources()
    install(install_path)


def build(
    build_dir: pathlib.Path = BUILD_DIR,
    src_dir: pathlib.Path = SRC_DIR,
    libs_dir: pathlib.Path = LIBS_DIR,
):
    build_dir.mkdir()
    print(f"Created {build_dir}")
    shutil.copytree(src_dir, build_dir, dirs_exist_ok=True)
    print(f"Copied {src_dir} to {build_dir}")
    shutil.copy2("metadata.txt", build_dir)
    print(f"Copied metadata.txt to {build_dir}")
    shutil.copytree(libs_dir, build_dir / "libs")


def verify_install_path(install_path: pathlib.Path):
    if "/QGIS/QGIS3/profiles/" not in install_path.as_posix():
        print("Provided plugin path argument doesn't look like a qgis path!")
        sys.exit(1)
    if install_path.name == "plugins":
        print("Specify plugin name in the install path.")
        sys.exit(1)


def install(install_path: pathlib.Path, build_dir: pathlib.Path = BUILD_DIR):
    shutil.move(build_dir, install_path)
    print(f"Installed plugin to {install_path}")


def uninstall(install_path: pathlib.Path):
    if "/QGIS/QGIS3/profiles/" not in install_path.as_posix():
        print("Provided plugin path argument doesn't look like a qgis path!")
        sys.exit(1)
    if os.path.exists(install_path):
        shutil.rmtree(install_path)
        print(f"Removed {install_path}")


def compile_resources(
    build_dir: pathlib.Path = BUILD_DIR, resource_path: pathlib.Path = RESOURCE_PATH
):

    output_path = build_dir / "resources.py"
    try:
        subprocess.run(
            [
                "pyrcc5",
                "-o",
                output_path,
                resource_path,
            ],
            check=True,
        )
        print(f"Compiled {resource_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error compiling resource files: {e}")
        sys.exit(1)


def patch_resources(build_dir: pathlib.Path = BUILD_DIR):
    p = build_dir / "ui/main.ui"
    # Read in the file
    with open(p, "r") as file:
        filedata = file.read()

    # Replace the target string
    filedata = filedata.replace("../../resources/resources.qrc", "resources.py")

    # Write the file out again
    with open(p, "w") as file:
        file.write(filedata)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("install_path", help="Path to qgis plugin directory")
    args = parser.parse_args()
    main(pathlib.Path(args.install_path).resolve())
