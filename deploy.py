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


def main(install_path: pathlib.Path, is_dist=False, is_test=False):
    if not install_path:
        print("Provide qgis plugin path")
        sys.exit(1)
    if not is_dist and not is_test:
        verify_install_path(install_path)
    uninstall(install_path)
    build(is_dist=is_dist, is_test=is_test)
    compile_resources()
    patch_resources()
    install(install_path)


def build(
    build_dir: pathlib.Path = BUILD_DIR,
    src_dir: pathlib.Path = SRC_DIR,
    is_dist: bool = False,
    is_test: bool = False,
):
    try:
        build_dir.mkdir()
        print(f"Created {build_dir}")
    except FileExistsError:
        print(f"{build_dir} already exists - deleting")
        shutil.rmtree(build_dir)
        build_dir.mkdir()
        print(f"Re-created empty {build_dir}")
    copy_kwargs = {"dirs_exist_ok": True}
    if is_dist:
        copy_kwargs["ignore"] = shutil.ignore_patterns("test")
    shutil.copytree(src_dir, build_dir, **copy_kwargs)
    print(f"Copied {src_dir} to {build_dir}")
    shutil.copy2("metadata.txt", build_dir)
    print(f"Copied metadata.txt to {build_dir}")
    shutil.copy2("LICENSE", build_dir)
    print(f"Copied LICENSE to {build_dir}")
    shutil.copy2("requirements.txt", build_dir)
    print(f"Copied requirements.txt to {build_dir}")
    if is_test:
        shutil.copytree(ROOT_DIR / ".docker", build_dir / ".docker")
        shutil.copy2(ROOT_DIR / ".coveragerc", build_dir / ".coveragerc")


def verify_install_path(install_path: pathlib.Path):
    if (
        "/QGIS/QGIS3/profiles/" not in install_path.as_posix()
        and "/QGIS/QGIS4/profiles/" not in install_path.as_posix()
    ):
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
    compiler = os.environ.get("PYRCC") or shutil.which("pyrcc5") or shutil.which("pyrcc6")
    if compiler is None:
        print("Could not find pyrcc5 or pyrcc6. Install a PyQt resource compiler or set PYRCC.")
        sys.exit(1)

    try:
        subprocess.run(
            [
                compiler,
                "-o",
                str(output_path),
                str(resource_path),
            ],
            check=True,
        )
        print(f"Compiled {resource_path} with {pathlib.Path(compiler).name}")
    except subprocess.CalledProcessError as e:
        print(f"Error compiling resource files: {e}")
        sys.exit(1)


def patch_resources(build_dir: pathlib.Path = BUILD_DIR):
    resources_py = build_dir / "resources.py"
    if resources_py.exists():
        filedata = resources_py.read_text(encoding="utf-8")
        filedata = filedata.replace("from PyQt5 import QtCore", "from qgis.PyQt import QtCore")
        filedata = filedata.replace("from PyQt6 import QtCore", "from qgis.PyQt import QtCore")
        resources_py.write_text(filedata, encoding="utf-8")

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
    parser.add_argument(
        "--test",
        action="store_true",
        help="Build for the docker/CI test container (includes test/, .docker/, .coveragerc; skips qgis profile path check).",
    )
    args = parser.parse_args()
    install_path = args.install_path or load_dotenv().get("EODH_QGIS_PATH")
    if not install_path:
        raise ValueError("Provide path to qgis plugin, either via argument or .env variable.")

    main(pathlib.Path(install_path).resolve(), args.dist, args.test)
