#!/usr/bin/env python3
"""
Test script to verify global library paths are working correctly.
"""

import os
import sys
from pathlib import Path

# Add app folder to path
script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parent.parent
app_root = repo_root / "app"
sys.path.insert(0, str(app_root))

from src.config import get_effective_library_paths, load_app_settings


def main():
    print("=" * 70)
    print("PRISM Global Library Paths - Verification")
    print("=" * 70)
    print()

    # Load app settings
    settings = load_app_settings(app_root=str(app_root))

    print("📋 App Settings:")
    print(f"  • Global Library Root: {settings.global_library_root}")
    print(f"  • Default Modalities:  {', '.join(settings.default_modalities)}")
    print()

    # Get effective paths
    lib_paths = get_effective_library_paths(
        app_root=str(app_root), app_settings=settings
    )

    print("🔍 Resolved Paths:")
    print(f"  • Library Root:  {lib_paths['global_library_root']}")
    print(f"  • Library Path:  {lib_paths['global_library_path']}")
    print(f"  • Recipe Path:   {lib_paths['global_recipe_path']}")
    print(f"  • Source:        {lib_paths['source']}")
    print()

    # Check if paths exist
    print("✅ Path Status:")
    checks = [
        ("Library Root", lib_paths["global_library_root"]),
        ("Library Path", lib_paths["global_library_path"]),
        ("Recipe Path", lib_paths["global_recipe_path"]),
    ]

    all_ok = True
    for label, path in checks:
        if path and os.path.exists(path):
            print(f"  ✓ {label}: EXISTS")
        elif path:
            print(f"  ✗ {label}: NOT FOUND")
            all_ok = False
        else:
            print(f"  ⚠ {label}: NOT CONFIGURED")
            all_ok = False
    print()

    # Count resources
    if lib_paths["global_library_path"]:
        library_path = Path(lib_paths["global_library_path"])

        surveys = []
        biometrics = []

        survey_dir = library_path / "survey"
        if survey_dir.exists():
            surveys = list(survey_dir.glob("*.json"))

        biometrics_dir = library_path / "biometrics"
        if biometrics_dir.exists():
            biometrics = list(biometrics_dir.glob("*.json"))

        print("📊 Library Resources:")
        print(f"  • Surveys:     {len(surveys)}")
        print(f"  • Biometrics:  {len(biometrics)}")
        print()

    if lib_paths["global_recipe_path"]:
        recipe_path = Path(lib_paths["global_recipe_path"])

        survey_recipes = []
        biometric_recipes = []

        survey_recipe_dir = recipe_path / "survey"
        if survey_recipe_dir.exists():
            survey_recipes = list(survey_recipe_dir.glob("*.json"))

        biometric_recipe_dir = recipe_path / "biometrics"
        if biometric_recipe_dir.exists():
            biometric_recipes = list(biometric_recipe_dir.glob("*.json"))

        print("📊 Recipe Resources:")
        print(f"  • Survey Recipes:     {len(survey_recipes)}")
        print(f"  • Biometric Recipes:  {len(biometric_recipes)}")
        print()

    print("=" * 70)
    if all_ok:
        print("✅ All global library paths are correctly configured!")
    else:
        print("⚠️  Some paths are missing or not configured.")
    print("=" * 70)


if __name__ == "__main__":
    main()
