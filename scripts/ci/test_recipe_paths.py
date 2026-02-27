#!/usr/bin/env python3
"""Test recipe path configuration without starting Flask server."""

import sys
from pathlib import Path

# Add app to path
script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parent.parent
app_root = repo_root / "app"
sys.path.insert(0, str(app_root))

from src.config import get_effective_library_paths

lib_paths = get_effective_library_paths(app_root=str(app_root))

print("=" * 70)
print("Recipe Path Configuration Test")
print("=" * 70)
print()
print("Configured paths:")
print(f"  • Library Root:  {lib_paths['global_library_root']}")
print(f"  • Library Path:  {lib_paths['global_library_path']}")
print(f"  • Recipe Path:   {lib_paths['global_recipe_path']}")
print(f"  • Source:        {lib_paths['source']}")
print()

# Verify recipe path
expected_recipe = str(repo_root / "official" / "recipe")
if lib_paths["global_recipe_path"] == expected_recipe:
    print("✅ CORRECT! Recipe path points to official/recipe")
else:
    print(f"❌ WRONG! Expected: {expected_recipe}")
    print(f"          Got:      {lib_paths['global_recipe_path']}")

# Check if recipes exist
if lib_paths["global_recipe_path"]:
    recipe_path = Path(lib_paths["global_recipe_path"])
    if recipe_path.exists():
        survey_recipes = recipe_path / "survey"
        if survey_recipes.exists():
            count = len(list(survey_recipes.glob("*.json")))
            print(f"📊 Found {count} survey recipes")

        bio_recipes = recipe_path / "biometrics"
        if bio_recipes.exists():
            count = len(list(bio_recipes.glob("*.json")))
            print(f"📊 Found {count} biometric recipes")

print()
print("=" * 70)
print("When you run recipe processing, it will use:")
print(f"  {lib_paths['global_recipe_path']}/survey/*.json")
print("=" * 70)
