#!/usr/bin/env python3
"""
Bundle pre-compiled pyedflib for Windows distribution.

This script downloads and extracts pre-compiled pyedflib wheels for Windows
to include in PRISM distributions for systems without C++ compilers.

Usage:
    python scripts/release/bundle_pyedflib.py

This will download wheels for common Python versions and extract them to vendor/
"""

import sys
import urllib.request
import zipfile
from pathlib import Path
import json


def get_pypi_releases():
    """Fetch available pyedflib releases from PyPI."""
    url = "https://pypi.org/pypi/pyedflib/json"
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read())
            return data["releases"]
    except Exception as e:
        print(f"Error fetching PyPI data: {e}")
        return None


def download_wheel(url, dest_dir):
    """Download a wheel file."""
    filename = url.split("/")[-1]
    dest_path = dest_dir / filename

    if dest_path.exists():
        print(f"  Already exists: {filename}")
        return dest_path

    print(f"  Downloading: {filename}")
    try:
        urllib.request.urlretrieve(url, dest_path)
        return dest_path
    except Exception as e:
        print(f"  Error downloading {filename}: {e}")
        return None


def extract_wheel(wheel_path, extract_dir):
    """Extract a wheel file (which is a ZIP file)."""
    print(f"  Extracting: {wheel_path.name}")
    try:
        with zipfile.ZipFile(wheel_path, "r") as zip_ref:
            # Extract only the package files, not metadata
            for member in zip_ref.namelist():
                if member.startswith("pyedflib/") or member.startswith("pyedflib-"):
                    zip_ref.extract(member, extract_dir)
        return True
    except Exception as e:
        print(f"  Error extracting {wheel_path.name}: {e}")
        return False


def main():
    """Main bundling process."""
    # Setup directories
    repo_root = Path(__file__).parent.parent
    vendor_dir = repo_root / "vendor"
    wheels_dir = vendor_dir / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PRISM - Bundle pyedflib for Windows")
    print("=" * 60)
    print()

    # Fetch available releases
    print("Fetching available releases from PyPI...")
    releases = get_pypi_releases()
    if not releases:
        print("ERROR: Could not fetch releases")
        return 1

    # Get latest version
    latest_version = max(releases.keys(), key=lambda v: [int(x) for x in v.split(".")])
    print(f"Latest version: {latest_version}")
    print()

    # Find Windows wheels for common Python versions
    wheels = []
    for file_info in releases[latest_version]:
        filename = file_info["filename"]
        # Look for Windows wheels (cp38, cp39, cp310, cp311)
        if (
            filename.endswith(".whl")
            and "win" in filename
            and any(f"cp{v}" in filename for v in ["38", "39", "310", "311"])
        ):
            wheels.append(file_info)

    if not wheels:
        print("ERROR: No Windows wheels found")
        return 1

    print(f"Found {len(wheels)} Windows wheels:")
    for w in wheels:
        print(f"  - {w['filename']}")
    print()

    # Download wheels
    print("Downloading wheels...")
    downloaded = []
    for wheel_info in wheels:
        wheel_path = download_wheel(wheel_info["url"], wheels_dir)
        if wheel_path:
            downloaded.append(wheel_path)
    print()

    if not downloaded:
        print("ERROR: No wheels downloaded")
        return 1

    # Extract wheels
    print("Extracting wheels...")
    for wheel_path in downloaded:
        extract_wheel(wheel_path, vendor_dir)
    print()

    # Create usage instructions
    instructions_path = vendor_dir / "USAGE.txt"
    with open(instructions_path, "w") as f:
        f.write(f"""
pyedflib Vendored Package - Usage Instructions
================================================

Version: {latest_version}
Downloaded: {len(downloaded)} Windows wheels

AUTOMATIC USAGE:
----------------
PRISM will automatically detect and use the vendored pyedflib if it cannot
import the system-installed version.

MANUAL INSTALLATION:
--------------------
If you need to install one of the bundled wheels manually:

1. Navigate to the wheels directory:
   cd vendor/wheels

2. Install the appropriate wheel for your Python version:
   # For Python 3.11 (64-bit Windows):
   pip install pyedflib-{latest_version}-cp311-cp311-win_amd64.whl
   
   # For Python 3.10 (64-bit Windows):
   pip install pyedflib-{latest_version}-cp310-cp310-win_amd64.whl

3. Check available wheels:
   dir (Windows) or ls (Mac/Linux)

DISTRIBUTION:
-------------
When distributing PRISM, include the entire vendor/ directory to provide
pyedflib support for Windows users without C++ compilers.

Files included: {len(downloaded)} wheel(s)
""")

    print("=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print(f"Downloaded: {len(downloaded)} wheels")
    print(f"Location: {wheels_dir}")
    print(f"Instructions: {instructions_path}")
    print()
    print("The vendored pyedflib will be automatically used if needed.")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
