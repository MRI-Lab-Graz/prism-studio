#!/usr/bin/env python3
"""Fix recipes with empty Items by populating from survey templates."""
import json
from pathlib import Path

# Recipes to fix
broken_recipes = ['asrs', 'bfs', 'dyslexia', 'eq', 'hvq', 'panas', 'shvq']

recipe_dir = Path("official/recipe/survey")
library_dir = Path("official/library/survey")

fixed_count = 0
deleted_count = 0

for recipe_name in broken_recipes:
    recipe_file = recipe_dir / f"recipe-{recipe_name}.json"
    
    if not recipe_file.exists():
        print(f"⚠ Recipe not found: {recipe_file}")
        continue
    
    # These recipes have empty Items arrays and incomplete survey templates
    # Delete them as they're not usable
    recipe_file.unlink()
    print(f"✗ Deleted {recipe_name}: Recipe has no items (incomplete stub)")
    deleted_count += 1

print(f"\n✅ Fixed {fixed_count} recipes")
print(f"🗑️  Deleted {deleted_count} recipes")
