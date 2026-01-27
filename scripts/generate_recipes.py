#!/usr/bin/env python3
"""
Generate recipe templates for all harvested surveys.

This script reads survey JSON files and creates corresponding recipe files
with basic structure that can be manually refined.
"""

import json
from pathlib import Path
from typing import Dict, List


def extract_reversed_items(survey_data: Dict) -> List[str]:
    """Extract items marked as reversed from survey."""
    reversed_items = []
    for key, value in survey_data.items():
        if isinstance(value, dict) and value.get('Reversed'):
            reversed_items.append(key)
    return reversed_items


def generate_recipe_template(survey_path: Path) -> Dict:
    """Generate a recipe template from a survey file."""
    with open(survey_path, 'r', encoding='utf-8') as f:
        survey = json.load(f)
    
    # Extract survey info
    study = survey.get('Study', {})
    survey_name = survey_path.stem.replace('survey-', '')
    
    # Get all item keys (exclude metadata sections)
    metadata_keys = {'Technical', 'I18n', 'Study', 'Metadata', 'Normative'}
    item_keys = [k for k in survey.keys() if k not in metadata_keys]
    
    # Find reversed items
    reversed_items = extract_reversed_items(survey)
    
    # Create recipe template
    recipe = {
        "RecipeVersion": "1.0.0",
        "Kind": "survey",
        "Survey": {
            "Name": study.get('ShortName', survey_name.upper()),
            "Reference": f"survey-{survey_name}.json"
        },
        "Transforms": {
            "Invert": {}
        },
        "Scores": {
            "Total": {
                "Description": {
                    "en": f"Total score for {study.get('OriginalName', {}).get('en', survey_name)}",
                    "de": f"Gesamtscore für {study.get('OriginalName', {}).get('de', survey_name)}"
                },
                "Items": item_keys,
                "Method": "sum",
                "Range": {
                    "min": len(item_keys),
                    "max": len(item_keys) * 7
                }
            }
        },
        "Psychometrics": {
            "Reliability": {
                "InternalConsistency": {
                    "CronbachAlpha": None,
                    "Note": "Add reliability data from validation studies"
                }
            },
            "Validity": {
                "Note": "Add validity evidence from original publication"
            }
        },
        "Usage": {
            "ScoringGuidelines": {
                "en": "Calculate total score by summing all items. Higher scores indicate higher levels of the measured construct.",
                "de": "Berechnen Sie den Gesamtscore durch Summierung aller Items. Höhere Werte bedeuten höhere Ausprägungen des gemessenen Konstrukts."
            },
            "InterpretationGuidelines": {
                "en": "Refer to original publication for interpretation guidelines and norms.",
                "de": "Siehe Originalpublikation für Interpretationsrichtlinien und Normen."
            }
        }
    }
    
    # Add reversed items if found
    if reversed_items:
        recipe["Transforms"]["Invert"]["ReverseCoded"] = {
            "Items": reversed_items,
            "OriginalRange": [1, 7],
            "Note": "These items are reverse-coded"
        }
    
    return recipe


def main():
    survey_dir = Path(__file__).parent.parent / 'official' / 'library' / 'survey'
    recipe_dir = Path(__file__).parent.parent / 'official' / 'recipe' / 'survey'
    recipe_dir.mkdir(parents=True, exist_ok=True)
    
    survey_files = sorted(survey_dir.glob('survey-*.json'))
    
    print(f"Generating recipes for {len(survey_files)} surveys...\n")
    
    success_count = 0
    skip_count = 0
    
    for survey_path in survey_files:
        survey_name = survey_path.stem.replace('survey-', '')
        recipe_path = recipe_dir / f'recipe-{survey_name}.json'
        
        # Skip if recipe already exists
        if recipe_path.exists():
            print(f"⊙ Skipping {survey_name} (recipe already exists)")
            skip_count += 1
            continue
        
        try:
            recipe = generate_recipe_template(survey_path)
            
            with open(recipe_path, 'w', encoding='utf-8') as f:
                json.dump(recipe, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Generated recipe-{survey_name}.json")
            success_count += 1
            
        except Exception as e:
            print(f"✗ Failed to generate recipe for {survey_name}: {e}")
    
    print(f"\n{'='*60}")
    print("Recipe generation complete:")
    print(f"  • {success_count} recipes created")
    print(f"  • {skip_count} skipped (already exist)")
    print(f"  • Output: {recipe_dir}")


if __name__ == "__main__":
    main()
