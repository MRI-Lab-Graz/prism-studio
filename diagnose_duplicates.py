#!/usr/bin/env python3
"""
Diagnose duplicate item IDs in survey templates.
Checks both official library and any project templates.
"""
import json
from pathlib import Path
from collections import defaultdict

def load_template_items(file_path):
    """Load items from a template file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {}
    
    items = {}
    IGNORE_KEYS = {"Technical", "Study", "Metadata", "Questions", "I18n", "Scoring", "Normative", "_aliases", "_reverse_aliases"}
    
    # Check if Questions section exists
    if "Questions" in data and isinstance(data["Questions"], dict):
        items = data["Questions"].copy()
    else:
        # Otherwise take all non-metadata keys
        items = {k: v for k, v in data.items() if k not in IGNORE_KEYS and isinstance(v, dict)}
    
    return items

def main():
    # Check official library
    print("=" * 80)
    print("SCANNING OFFICIAL LIBRARY")
    print("=" * 80)
    
    library_path = Path('official/library/survey')
    all_items = defaultdict(list)
    
    for file_path in sorted(library_path.glob("*.json")):
        items = load_template_items(file_path)
        for item_id in items.keys():
            all_items[item_id].append(file_path.name)
    
    # Find duplicates
    duplicates = {k: v for k, v in all_items.items() if len(v) > 1}
    
    if duplicates:
        print(f"\n✗ Found {len(duplicates)} duplicate item IDs across survey templates:\n")
        for item_id, files in sorted(duplicates.items()):
            print(f"  • {item_id}: {', '.join(files)}")
            # Show which fields they define
            for file in files:
                file_path = library_path / file
                items = load_template_items(file_path)
                if item_id in items:
                    item_def = items[item_id]
                    fields = []
                    if "Description" in item_def:
                        fields.append(f"Description: {item_def['Description']}")
                    if "Levels" in item_def:
                        fields.append(f"Levels: {list(item_def['Levels'].keys()) if isinstance(item_def['Levels'], dict) else item_def['Levels']}")
                    if "Type" in item_def:
                        fields.append(f"Type: {item_def['Type']}")
                    if fields:
                        print(f"      {file}: {'; '.join(fields)}")
    else:
        print("\n✓ No duplicate item IDs found in the official library.")
    
    print("\n" + "=" * 80)
    print("CHECKING PROJECT TEMPLATES")
    print("=" * 80)
    
    # Check if there are project-specific templates
    demo_path = Path('demo')
    if demo_path.exists():
        print(f"\nScanning {demo_path}...")
        project_items = defaultdict(list)
        for file_path in demo_path.rglob("survey-*.json"):
            items = load_template_items(file_path)
            for item_id in items.keys():
                project_items[item_id].append(str(file_path))
        
        if project_items:
            project_dups = {k: v for k, v in project_items.items() if len(v) > 1}
            if project_dups:
                print(f"\n✗ Found {len(project_dups)} duplicate item IDs in project templates:")
                for item_id, files in sorted(project_dups.items()):
                    print(f"  • {item_id}: {', '.join(files)}")

if __name__ == "__main__":
    main()
