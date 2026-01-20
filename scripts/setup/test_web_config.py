#!/usr/bin/env python3
"""Test if prism-studio.py loads with correct global library paths."""

import sys
from pathlib import Path

# Add app to path
script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parent.parent
app_root = repo_root / "app"
sys.path.insert(0, str(app_root))

# Import the configuration
from src.config import get_effective_library_paths

# Simulate what prism-studio.py does
BASE_DIR = app_root
lib_paths = get_effective_library_paths(app_root=str(BASE_DIR))

print("=" * 70)
print("PRISM Studio - Global Library Configuration Test")
print("=" * 70)
print()

if lib_paths["global_library_path"]:
    survey_library_path = Path(lib_paths["global_library_path"])
    print(f"✅ Using global library: {survey_library_path}")
else:
    survey_library_path = BASE_DIR / "survey_library"
    print(f"⚠️  Using fallback library: {survey_library_path}")

print()
print("Resolved paths:")
print(f"  • Library Root:  {lib_paths['global_library_root']}")
print(f"  • Library Path:  {lib_paths['global_library_path']}")
print(f"  • Recipe Path:   {lib_paths['global_recipe_path']}")
print(f"  • Source:        {lib_paths['source']}")
print()

# Check if path exists
if survey_library_path.exists():
    survey_dir = survey_library_path / "survey"
    if survey_dir.exists():
        survey_count = len(list(survey_dir.glob("*.json")))
        print(f"📊 Found {survey_count} surveys in library")
    else:
        print(f"⚠️  No survey/ subdirectory found in {survey_library_path}")
else:
    print(f"❌ Library path does not exist: {survey_library_path}")

print()
print("=" * 70)
print("✅ Configuration test complete!")
print("=" * 70)
