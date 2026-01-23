#!/usr/bin/env python3
"""Fix recipe Scores format from object to list."""
import json
from pathlib import Path

recipe_dir = Path("official/recipe/survey")
fixed_count = 0
errors = []

for recipe_file in sorted(recipe_dir.glob("recipe-*.json")):
    try:
        with open(recipe_file, 'r', encoding='utf-8') as f:
            recipe = json.load(f)
        
        modified = False
        
        # Fix: Convert Scores from object to list format
        if "Scores" in recipe and isinstance(recipe["Scores"], dict):
            old_scores = recipe["Scores"]
            new_scores = []
            
            for score_name, score_data in old_scores.items():
                if not isinstance(score_data, dict):
                    continue
                
                # Create new score object with Name property
                new_score = {"Name": score_name}
                
                # Copy all properties
                for key, value in score_data.items():
                    if key == "Description" and isinstance(value, dict):
                        # Convert multilingual description to English string
                        new_score["Description"] = value.get("en", value.get("de", str(value)))
                    else:
                        new_score[key] = value
                
                new_scores.append(new_score)
            
            recipe["Scores"] = new_scores
            modified = True
            print(f"✓ Converted Scores to list format in {recipe_file.name}")
        
        # Save if modified
        if modified:
            with open(recipe_file, 'w', encoding='utf-8') as f:
                json.dump(recipe, f, indent=2, ensure_ascii=False)
            fixed_count += 1
    
    except Exception as e:
        errors.append(f"Error processing {recipe_file.name}: {e}")

print(f"\n✅ Fixed {fixed_count} recipe files")
if errors:
    print(f"\n❌ Errors:")
    for err in errors:
        print(f"  {err}")
