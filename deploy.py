#!/bin/python3

import argparse
import os
import pathlib
import shutil
import subprocess
import sys

ROOT_DIR = pathlib.Path(__file__).parent.resolve()
BUILD_DIR = ROOT_DIR / "build"
SRC_DIR = ROOT_DIR / "eodh_qgis"
RESOURCE_PATH = ROOT_DIR / "resources/resources.qrc"


def main(install_path: pathlib.Path, is_dist=False):
    if not install_path:
        print("Provide qgis plugin path")
        sys.exit(1)
    if not is_dist:
        verify_install_path(install_path)
    uninstall(install_path)
    build()
    compile_resources()
    patch_resources()
    install(install_path)


def build(
    build_dir: pathlib.Path = BUILD_DIR,
    src_dir: pathlib.Path = SRC_DIR,
):
    try:
        build_dir.mkdir()
        print(f"Created {build_dir}")
    except FileExistsError:
        print(f"{build_dir} already exists - deleting")
        shutil.rmtree(build_dir)
        build_dir.mkdir()
        print(f"Re-created empty {build_dir}")
    shutil.copytree(src_dir, build_dir, dirs_exist_ok=True)
    print(f"Copied {src_dir} to {build_dir}")
    shutil.copy2("metadata.txt", build_dir)
    print(f"Copied metadata.txt to {build_dir}")
    shutil.copy2("LICENSE", build_dir)
    print(f"Copied LICENSE to {build_dir}")
    shutil.copy2("requirements.txt", build_dir)
    print(f"Copied requirements.txt to {build_dir}")
    shutil.copytree(ROOT_DIR / ".docker", build_dir / ".docker")
    shutil.copy2(ROOT_DIR / ".coveragerc", build_dir / ".coveragerc")


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
    if os.path.exists(install_path):
        shutil.rmtree(install_path)
        print(f"Removed {install_path}")


def compile_resources(build_dir: pathlib.Path = BUILD_DIR, resource_path: pathlib.Path = RESOURCE_PATH):
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
    # Patch all .ui files that reference the resources.qrc file
    ui_files = [
        build_dir / "ui/main.ui",
        build_dir / "ui/landing.ui",
    ]

    for p in ui_files:
        if not p.exists():
            continue
        # Read in the file
        with open(p) as file:
            filedata = file.read()

        # Replace resource references - handle different relative paths
        filedata = filedata.replace("../../resources/resources.qrc", "resources.py")
        filedata = filedata.replace("../../../resources/resources.qrc", "resources.py")

        # Write the file out again
        with open(p, "w") as file:
            file.write(filedata)


def load_dotenv():
    if not os.path.isfile(".env"):
        return {}
    with open(".env") as file:
        lines = file.read().splitlines()

    dotenv_vars = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", maxsplit=1)
        dotenv_vars[key] = value.strip('"')

    return dotenv_vars


if __name__ == "__main__":
    print(sys.version)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "install_path",
        nargs="?",
        help=("Path to qgis plugin directory, if not provided, looks for EODH_QGIS_PATH in .env file."),
    )
    parser.add_argument("--dist", action="store_true", help="Use this when building a release package.")
    args = parser.parse_args()
    install_path = args.install_path or load_dotenv().get("EODH_QGIS_PATH")
    if not install_path:
        raise ValueError("Provide path to qgis plugin, either via argument or .env variable.")

    main(pathlib.Path(install_path).resolve(), args.dist)
