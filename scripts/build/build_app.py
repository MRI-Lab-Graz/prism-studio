import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__


def _maybe_rm_tree(path: Path) -> None:
    try:
        if path.exists():
            shutil.rmtree(path)
    except Exception:
        pass


def _generate_icon(name: str) -> str | None:
    """Best-effort icon generation.

    - macOS: generates an .icns from static/img/MRI_Lab_Logo.png using sips + iconutil
    - Windows: uses the PNG directly (PyInstaller can convert)
    """
    source_png = Path("static/img/MRI_Lab_Logo.png")
    if not source_png.exists():
        print(f"⚠️ Icon source not found: {source_png}")
        return None

    if sys.platform == "darwin":
        print("🎨 Generating macOS icon (.icns)...")
        iconset_dir = Path(f"{name}.iconset")
        try:
            _maybe_rm_tree(iconset_dir)
            iconset_dir.mkdir(parents=True, exist_ok=True)

            sizes = [16, 32, 64, 128, 256, 512, 1024]
            for size in sizes:
                subprocess.run(
                    [
                        "sips",
                        "-z",
                        str(size),
                        str(size),
                        str(source_png),
                        "--out",
                        str(iconset_dir / f"icon_{size}x{size}.png"),
                    ],
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    [
                        "sips",
                        "-z",
                        str(size * 2),
                        str(size * 2),
                        str(source_png),
                        "--out",
                        str(iconset_dir / f"icon_{size}x{size}@2x.png"),
                    ],
                    check=True,
                    capture_output=True,
                )

            icns_path = Path(f"{name}.icns")
            if icns_path.exists():
                icns_path.unlink()
            subprocess.run(["iconutil", "-c", "icns", str(iconset_dir)], check=True)
            _maybe_rm_tree(iconset_dir)
            if icns_path.exists():
                print(f"✅ Generated {icns_path}")
                return str(icns_path)
        except Exception as e:
            print(f"⚠️ Failed to generate icon: {e}")
        finally:
            _maybe_rm_tree(iconset_dir)

        return None

    if sys.platform == "win32":
        print("🎨 Using PNG icon for Windows...")
        return str(source_png)

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Prism Validator using PyInstaller")
    parser.add_argument(
        "--entry",
        default="prism-validator-web.py",
        help="Entry script to package (default: prism-validator-web.py)",
    )
    parser.add_argument(
        "--name",
        default="PrismValidator",
        help="App name (default: PrismValidator)",
    )
    parser.add_argument(
        "--mode",
        choices=["onefile", "onedir"],
        default="onefile",
        help="Distribution mode (default: onefile)",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Keep a console window (default: windowed)",
    )
    parser.add_argument(
        "--no-icon",
        action="store_true",
        help="Skip icon generation",
    )
    parser.add_argument(
        "--no-sign",
        action="store_true",
        help="Skip macOS post-build codesign/xattr fixes",
    )
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete build/ and dist/ before building",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    os.chdir(project_root)

    # Clean previous builds (optional)
    if args.clean_output:
        _maybe_rm_tree(project_root / "build")
        _maybe_rm_tree(project_root / "dist")

    # Ensure optional runtime dirs exist so they can be bundled.
    (project_root / "survey_library").mkdir(parents=True, exist_ok=True)

    icon_file = None
    if not args.no_icon:
        icon_file = _generate_icon(args.name)

    # On Windows use ; as separator, on Unix use :
    sep = ";" if os.name == "nt" else ":"

    datas = [
        f"templates{sep}templates",
        f"static{sep}static",
        f"schemas{sep}schemas",
        f"src{sep}src",
    ]
    if (project_root / "survey_library").exists():
        datas.append(f"survey_library{sep}survey_library")
        print("✓ Including survey_library")

    pyinstaller_args = [
        args.entry,
        f"--name={args.name}",
        "--clean",
        "--noconfirm",
        # Explicitly include hidden imports that PyInstaller might miss
        "--hidden-import=jsonschema",
        "--hidden-import=xml.etree.ElementTree",
    ]

    if not args.console:
        pyinstaller_args.append("--windowed")
    if args.mode == "onefile":
        pyinstaller_args.append("--onefile")
    else:
        pyinstaller_args.append("--onedir")

    if sys.platform == "darwin":
        pyinstaller_args.append("--osx-bundle-identifier=at.ac.uni-graz.mri.prism-validator")

    if icon_file:
        pyinstaller_args.append(f"--icon={icon_file}")

    for data in datas:
        pyinstaller_args.append(f"--add-data={data}")

    print("Building with args:", pyinstaller_args)
    PyInstaller.__main__.run(pyinstaller_args)

    # --- Post-Build Platform-Specific Fixes ---
    if sys.platform == "darwin":
        app_path = str(project_root / "dist" / f"{args.name}.app")
        print("🔧 Applying macOS post-build fixes...")

        # 1) Update Info.plist with LSMinimumSystemVersion
        try:
            print("📝 Updating Info.plist...")
            plist_path = os.path.join(app_path, "Contents", "Info.plist")
            subprocess.run(
                [
                    "plutil",
                    "-replace",
                    "LSMinimumSystemVersion",
                    "-string",
                    "10.13",
                    plist_path,
                ],
                check=True,
            )
        except Exception as e:
            print(f"⚠️ Updating Info.plist failed: {e}")

        if not args.no_sign:
            # 2) Force ad-hoc code signing
            try:
                print("🔏 Signing app bundle...")
                subprocess.run(["codesign", "--force", "--deep", "--sign", "-", app_path], check=True)
            except Exception as e:
                print(f"⚠️ Signing failed: {e}")

            # 3) Remove quarantine attribute (helps avoid 'App is damaged' in some cases)
            try:
                print("🛡️ Removing quarantine attribute...")
                subprocess.run(["xattr", "-cr", app_path], check=True)
            except Exception as e:
                print(f"⚠️ Removing quarantine failed: {e}")

        print(f"\n✅ Build complete! Check dist/{args.name}.app")
        print(f"   To run: open dist/{args.name}.app")

    elif sys.platform == "win32":
        print(f"\n✅ Build complete! Check dist\\{args.name}\\")
        print(f"   To run: dist\\{args.name}\\{args.name}.exe")
    else:
        print(f"\n✅ Build complete! Check dist/{args.name}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
