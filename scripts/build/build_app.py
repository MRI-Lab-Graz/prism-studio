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


def _get_version() -> str:
    """Extract version from app/src/__init__.py"""
    try:
        init_path = Path(__file__).resolve().parents[2] / "app" / "src" / "__init__.py"
        with open(init_path, "r") as f:
            for line in f:
                if line.startswith("__version__"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "1.0.0"


def _parse_version_tuple(version: str) -> tuple[int, int, int, int]:
    """Convert semantic version (possibly with beta/rc suffix) into 4-int tuple.

    Examples:
    - "1.8.2b4" -> (1, 8, 2, 0)
    - "1.8.2"   -> (1, 8, 2, 0)
    - "1.8"     -> (1, 8, 0, 0)
    """
    raw_parts = version.split(".")
    cleaned: list[int] = []
    for part in raw_parts:
        digits = "".join(ch for ch in part if ch.isdigit())
        if digits == "":
            cleaned.append(0)
        else:
            cleaned.append(int(digits))
    while len(cleaned) < 4:
        cleaned.append(0)
    return tuple(cleaned[:4])


def _generate_version_info(name: str, version: str) -> str:
    """Generates a Windows version info file for PyInstaller."""
    v_tuple = _parse_version_tuple(version)

    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v_tuple},
    prodvers={v_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'MRI-Lab-Graz'),
        StringStruct(u'FileDescription', u'{name}'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'InternalName', u'{name}'),
        StringStruct(u'LegalCopyright', u'Copyright (c) 2025 MRI-Lab-Graz'),
        StringStruct(u'OriginalFilename', u'{name}.exe'),
        StringStruct(u'ProductName', u'{name}'),
        StringStruct(u'ProductVersion', u'{version}')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    version_file = Path(f"{name}_version.txt")
    version_file.write_text(content, encoding="utf-8")
    return str(version_file)


def _generate_icon(name: str) -> str | None:
    """Best-effort icon generation.

    - macOS: generates an .icns from app/static/img/MRI_Lab_Logo.png using sips + iconutil
    - Windows: uses the PNG directly (PyInstaller can convert)
    """
    # Use absolute paths or correctly join with project root if needed
    source_png = Path("app/static/img/MRI_Lab_Logo.png")
    if not source_png.exists():
        # Fallback to local if running from inside app/
        source_png = Path("static/img/MRI_Lab_Logo.png")
        
    if not source_png.exists():
        print("[WARN] Icon source not found at app/static/img/MRI_Lab_Logo.png or static/img/MRI_Lab_Logo.png")
        return None

    if sys.platform == "darwin":
        print("[ICON] Generating macOS icon (.icns)...")
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
                print(f"[OK] Generated {icns_path}")
                return str(icns_path)
        except Exception as e:
            print(f"[WARN] Failed to generate icon: {e}")
        finally:
            _maybe_rm_tree(iconset_dir)

        return None

    if sys.platform == "win32":
        print("[ICON] Using PNG icon for Windows...")
        return str(source_png)

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Prism Validator using PyInstaller"
    )
    parser.add_argument(
        "--entry",
        default="prism-studio.py",
        help="Entry script to package (default: prism-studio.py)",
    )
    parser.add_argument(
        "--name",
        default="PrismValidator",
        help="App name (default: PrismValidator)",
    )
    parser.add_argument(
        "--mode",
        choices=["onefile", "onedir"],
        default="onedir",
        help="Distribution mode (default: onedir)",
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
    parser.add_argument(
        "--target-arch",
        choices=["x86_64", "arm64", "universal2"],
        default=None,
        help="Target architecture for macOS (default: current architecture)",
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

    version = _get_version()
    print(f"[BUILD] Building {args.name} version {version}")

    icon_file = None
    if not args.no_icon:
        icon_file = _generate_icon(args.name)

    version_file = None
    if sys.platform == "win32":
        version_file = _generate_version_info(args.name, version)

    # PyInstaller separator: ; on Windows, : on Unix
    sep = ";" if os.name == "nt" else ":"

    # Data paths are now in the app/ subdirectory
    # We use os.path.join for the source path to be platform-neutral, 
    # then the PyInstaller 'sep' to separate source and destination.
    datas = [
        f"{os.path.join('app', 'templates')}{sep}templates",
        f"{os.path.join('app', 'static')}{sep}static",
        f"{os.path.join('app', 'schemas')}{sep}schemas",
        f"{os.path.join('app', 'src')}{sep}src",
    ]
    
    # Include official library and recipe folders
    if (project_root / "official").exists():
        datas.append(f"official{sep}official")
        print("[OK] Including official/ folder (library and recipes)")
    
    # Check for optional directories and only add them if they exist
    if (project_root / "app" / "survey_library").exists():
        datas.append(f"{os.path.join('app', 'survey_library')}{sep}survey_library")
        print("[OK] Including survey_library")
    elif (project_root / "survey_library").exists():
        datas.append(f"survey_library{sep}survey_library")
        print("[OK] Including survey_library (from root)")

    pyinstaller_args = [
        f"--name={args.name}",
        "--clean",
        "--noconfirm",
        # Explicitly include hidden imports that PyInstaller might miss
        "--hidden-import=jsonschema",
        "--hidden-import=xml.etree.ElementTree",
        "--hidden-import=flask",
    ]

    if not args.console:
        pyinstaller_args.append("--windowed")
    if args.mode == "onefile":
        pyinstaller_args.append("--onefile")
    else:
        pyinstaller_args.append("--onedir")

    if sys.platform == "darwin":
        pyinstaller_args.append(
            "--osx-bundle-identifier=at.ac.uni-graz.mri.prism-studio"
        )
        if args.target_arch:
            pyinstaller_args.append(f"--target-architecture={args.target_arch}")
            print(f"[BUILD] Setting target architecture to: {args.target_arch}")

    if icon_file:
        pyinstaller_args.append(f"--icon={icon_file}")

    if version_file:
        pyinstaller_args.append(f"--version-file={version_file}")

    for data in datas:
        pyinstaller_args.append(f"--add-data={data}")

    # The entry script must be the last positional argument
    pyinstaller_args.append(args.entry)

    print("Building with args:", pyinstaller_args)
    PyInstaller.__main__.run(pyinstaller_args)

    # --- Post-Build Platform-Specific Fixes ---
    if sys.platform == "darwin":
        app_path = str(project_root / "dist" / f"{args.name}.app")
        print("[BUILD] Applying macOS post-build fixes...")

        # 1) Update Info.plist with LSMinimumSystemVersion
        try:
            print("[PLIST] Updating Info.plist...")
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
            print(f"[WARN] Updating Info.plist failed: {e}")

        if not args.no_sign:
            # 2) Force ad-hoc code signing
            try:
                print("[SIGN] Signing app bundle...")
                subprocess.run(
                    ["codesign", "--force", "--deep", "--sign", "-", app_path],
                    check=True,
                )
            except Exception as e:
                print(f"[WARN] Signing failed: {e}")

            # 3) Remove quarantine attribute (helps avoid 'App is damaged' in some cases)
            try:
                print("[XATTR] Removing quarantine attribute...")
                subprocess.run(["xattr", "-cr", app_path], check=True)
            except Exception as e:
                print(f"[WARN] Removing quarantine failed: {e}")

        print(f"\n[OK] Build complete! Check dist/{args.name}.app")
        print(f"   To run: open dist/{args.name}.app")

    elif sys.platform == "win32":
        print(f"\n[OK] Build complete! Check dist\\{args.name}\\")
        print(f"   To run: dist\\{args.name}\\{args.name}.exe")
    else:
        print(f"\n[OK] Build complete! Check dist/{args.name}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
