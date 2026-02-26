#!/usr/bin/env python3
"""
Quick test to verify the API returns correct library paths.
"""

import sys
import os
from pathlib import Path

# Suppress Flask app initialization
os.environ["WERKZEUG_RUN_MAIN"] = "true"

# Add app to path
script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parent.parent
app_root = repo_root / "app"
sys.path.insert(0, str(app_root))

# Simulate what the API endpoint does
from src.config import load_app_settings, get_effective_library_paths

app_root_str = str(app_root)
settings = load_app_settings(app_root=app_root_str)

# Get effective library path from configuration
lib_paths = get_effective_library_paths(app_root=app_root_str, app_settings=settings)
default_library_path = lib_paths["global_library_path"] or str(
    Path(app_root) / "survey_library"
)

print("=" * 70)
print("PRISM Studio API - Library Path Test")
print("=" * 70)
print()
print("What the API will return:")
print(f"  • default_library_path: {default_library_path}")
print(f"  • global_template_library_path: {settings.global_template_library_path}")
print()
print("Expected in UI:")
print(f"  Default: {default_library_path}")
print()
print("Full library paths:")
print(f"  • Library Root: {lib_paths['global_library_root']}")
print(f"  • Library Path: {lib_paths['global_library_path']}")
print(f"  • Recipe Path:  {lib_paths['global_recipe_path']}")
print(f"  • Source:       {lib_paths['source']}")
print()
print("=" * 70)

# Verify it's correct
expected = str(repo_root / "official" / "library")
if default_library_path == expected:
    print("✅ CORRECT! Path matches expected official/library")
else:
    print(f"❌ WRONG! Expected: {expected}")
    print(f"          Got:      {default_library_path}")
print("=" * 70)
