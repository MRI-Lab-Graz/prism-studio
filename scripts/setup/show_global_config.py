#!/usr/bin/env python3
"""
Show current PRISM global library configuration.

Quick utility to display the effective global library paths.
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
    settings = load_app_settings(app_root=str(app_root))
    lib_paths = get_effective_library_paths(
        app_root=str(app_root), app_settings=settings
    )

    print()
    print("PRISM Global Library Configuration")
    print("=" * 50)
    print()

    if lib_paths["global_library_root"]:
        print(f"📁 Library Root:  {lib_paths['global_library_root']}")
        print(f"📋 Library Path:  {lib_paths['global_library_path']}")
        print(f"🧪 Recipe Path:   {lib_paths['global_recipe_path']}")
        print(f"🔧 Source:        {lib_paths['source']}")
    else:
        print("⚠️  No global library configured")

    print()

    # Quick resource count
    if lib_paths["global_library_path"] and os.path.exists(
        lib_paths["global_library_path"]
    ):
        survey_dir = Path(lib_paths["global_library_path"]) / "survey"
        if survey_dir.exists():
            survey_count = len(list(survey_dir.glob("*.json")))
            print(f"📊 Surveys: {survey_count}")

    if lib_paths["global_recipe_path"] and os.path.exists(
        lib_paths["global_recipe_path"]
    ):
        recipe_dir = Path(lib_paths["global_recipe_path"]) / "survey"
        if recipe_dir.exists():
            recipe_count = len(list(recipe_dir.glob("*.json")))
            print(f"📊 Recipes: {recipe_count}")

    print()


if __name__ == "__main__":
    main()
