#!/usr/bin/env python3
import json
from pathlib import Path
from collections import defaultdict

library_path = Path("official/library/survey")

IGNORE_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    "Questions",
    "I18n",
    "Scoring",
    "Normative",
}


def iter_template_items(file_path):
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return

    if "Questions" in data and isinstance(data["Questions"], dict):
        items = data["Questions"]
    elif isinstance(data, dict):
        items = {k: v for k, v in data.items() if k not in IGNORE_KEYS}
    else:
        return

    for item_id, item_def in items.items():
        yield item_id, item_def


# Check all files
target_ids = {"2D_l", "2D_r", "4D_r", "4d_l"}
found_items: dict[str, list[dict[str, object]]] = {}

for file_path in sorted(library_path.glob("*.json")):
    if not (
        file_path.name.startswith("survey-") or file_path.name.startswith("biometrics-")
    ):
        continue

    for item_id, item_def in iter_template_items(file_path):
        if item_id in target_ids:
            if item_id not in found_items:
                found_items[item_id] = []
            found_items[item_id].append({"file": file_path.name, "def": item_def})

if found_items:
    print("Found the following duplicate item IDs:\n")
    for item_id, locations in sorted(found_items.items()):
        print(f"\nItem ID: {item_id}")
        print(f"  Found in {len(locations)} file(s):")
        for loc in locations:
            print(f"    - {loc['file']}")
            print(f"      Definition: {json.dumps(loc['def'], indent=8)}")
else:
    print("No matching item IDs found. Let me check what items exist...\n")

    # List all item IDs in library
    all_items = defaultdict(list)
    for file_path in sorted(library_path.glob("*.json")):
        if not (
            file_path.name.startswith("survey-")
            or file_path.name.startswith("biometrics-")
        ):
            continue
        for item_id, _ in iter_template_items(file_path):
            all_items[item_id].append(file_path.name)

    # Find items that appear in multiple files
    duplicates = {k: v for k, v in all_items.items() if len(v) > 1}
    if duplicates:
        print(f"Found {len(duplicates)} item IDs appearing in multiple files:\n")
        for item_id, files in sorted(duplicates.items()):
            print(f"  {item_id}: {files}")
    else:
        print("No duplicate item IDs found in the library.")
