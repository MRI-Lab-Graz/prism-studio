#!/usr/bin/env python3
"""
Configure global library paths to point to the official folder.

This script sets up the app-level settings to use the official/ folder
as the global library and recipe source for all PRISM projects.
"""

import sys
from pathlib import Path

# Add app folder to path
script_dir = Path(__file__).resolve().parent
app_root = script_dir.parent.parent / "app"
sys.path.insert(0, str(app_root))

from src.config import AppSettings, save_app_settings, get_effective_library_paths


def main():
    """Configure global library paths."""
    
    # Get the repository root (parent of app/)
    repo_root = app_root.parent
    official_root = repo_root / "official"
    
    print("=" * 70)
    print("PRISM Global Library Configuration")
    print("=" * 70)
    print()
    
    # Check that official folder exists
    if not official_root.exists():
        print(f"❌ Error: Official folder not found at: {official_root}")
        print()
        print("   Expected structure:")
        print(f"   {official_root}/")
        print("   ├── library/")
        print("   │   ├── survey/")
        print("   │   └── biometrics/")
        print("   └── recipe/")
        print("       ├── surveys/")
        print("       └── biometrics/")
        sys.exit(1)
    
    # Check subdirectories
    library_dir = official_root / "library"
    recipe_dir = official_root / "recipe"
    
    warnings = []
    if not library_dir.exists():
        warnings.append(f"⚠️  Library directory not found: {library_dir}")
    if not recipe_dir.exists():
        warnings.append(f"⚠️  Recipe directory not found: {recipe_dir}")
    
    # Create app settings
    settings = AppSettings(
        global_library_root=str(official_root),
        default_modalities=["survey", "biometrics"]
    )
    
    # Save settings to app folder
    settings_path = save_app_settings(settings, app_root=str(app_root))
    
    print("✅ Global library root configured:")
    print(f"   {official_root}")
    print()
    print("📝 Settings saved to:")
    print(f"   {settings_path}")
    print()
    
    if warnings:
        print("⚠️  Warnings:")
        for warning in warnings:
            print(f"   {warning}")
        print()
    
    # Verify configuration
    print("🔍 Verifying configuration...")
    lib_paths = get_effective_library_paths(app_root=str(app_root), app_settings=settings)
    
    print()
    print("Resolved paths:")
    print(f"  • Library root:  {lib_paths['global_library_root']}")
    print(f"  • Library path:  {lib_paths['global_library_path']}")
    print(f"  • Recipe path:   {lib_paths['global_recipe_path']}")
    print(f"  • Source:        {lib_paths['source']}")
    print()
    
    # Count resources
    survey_count = 0
    recipe_count = 0
    
    if library_dir.exists():
        survey_dir = library_dir / "survey"
        if survey_dir.exists():
            survey_count = len(list(survey_dir.glob("*.json")))
    
    if recipe_dir.exists():
        survey_recipe_dir = recipe_dir / "survey"
        if survey_recipe_dir.exists():
            recipe_count = len(list(survey_recipe_dir.glob("*.json")))
    
    print("📊 Available resources:")
    print(f"  • Surveys:  {survey_count}")
    print(f"  • Recipes:  {recipe_count}")
    print()
    
    print("=" * 70)
    print("✅ Configuration complete!")
    print()
    print("All PRISM tools will now use the official folder as the")
    print("global library source by default.")
    print()
    print("Individual projects can still override this by setting")
    print("templateLibraryPath in their .prismrc.json file.")
    print("=" * 70)


if __name__ == "__main__":
    main()
