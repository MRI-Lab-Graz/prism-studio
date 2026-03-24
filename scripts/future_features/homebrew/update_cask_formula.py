#!/usr/bin/env python3
"""
Update Homebrew cask formula with actual SHA256 checksums from release artifacts.

Usage:
    python scripts/future_features/homebrew/update_cask_formula.py <version> <arm64_zip> <x86_64_zip>

Example:
    python scripts/future_features/homebrew/update_cask_formula.py 1.13.0 \
        prism-studio-macOS-arm64.zip \
        prism-studio-macOS-x86_64.zip
"""

import sys
import hashlib
from pathlib import Path


def calculate_sha256(file_path: str) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def update_cask_formula(
    version: str, arm64_zip: str, x86_64_zip: str, output_path: str = None
) -> str:
    """
    Update the cask formula with actual checksums.

    Returns the updated cask content as a string.
    """
    if output_path is None:
        output_path = "scripts/future_features/homebrew/prism-studio.rb"

    # Calculate checksums
    print(f"Calculating SHA256 for {arm64_zip}...")
    sha256_arm = calculate_sha256(arm64_zip)
    print(f"  ✓ {sha256_arm}")

    print(f"Calculating SHA256 for {x86_64_zip}...")
    sha256_intel = calculate_sha256(x86_64_zip)
    print(f"  ✓ {sha256_intel}")

    # Read template
    with open(output_path, "r") as f:
        content = f.read()

    # Replace placeholders
    content = content.replace("VERSION_PLACEHOLDER", version)
    content = content.replace("SHA256_ARM64_PLACEHOLDER", sha256_arm)
    content = content.replace("SHA256_X86_64_PLACEHOLDER", sha256_intel)

    # Write updated formula
    with open(output_path, "w") as f:
        f.write(content)

    print(f"\n✓ Updated {output_path}")
    return content


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Usage: python scripts/future_features/homebrew/update_cask_formula.py <version> <arm64_zip> <x86_64_zip>"
        )
        sys.exit(1)

    version, arm64_zip, x86_64_zip = sys.argv[1:4]

    try:
        update_cask_formula(version, arm64_zip, x86_64_zip)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
