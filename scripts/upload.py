from qgispluginci.release import upload_plugin_to_osgeo
import argparse
import sys

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--osgeo-username", type=str, required=True)
    parser.add_argument("--osgeo-password", type=str, required=True)
    parser.add_argument("--plugin-path", type=str, required=True)
    args = parser.parse_args()

    if not args.osgeo_username or not args.osgeo_password or not args.plugin_path:
        print(
            "Error: --osgeo-username, --osgeo-password and --plugin-path are required"
        )
        sys.exit(1)

    upload_plugin_to_osgeo(args.osgeo_username, args.osgeo_password, args.plugin_path)
