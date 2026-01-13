#!/usr/bin/env python3
"""
Combine multiple Prism survey JSON templates into a single sidecar.

Usage:
    python combine_survey_json.py --output task-combined_beh.json template1.json template2.json ...

This script is useful when a single BIDS task contains multiple questionnaires
(e.g., a single "survey" task run containing BDI, STAI, and PSQI).
"""

import os
import json
import argparse
from datetime import date


def combine_jsons(template_paths, output_path):
    """
    Merge multiple JSON sidecars.
    """
    combined_data = {}

    # Base structure (will be updated by the first template)
    combined_data = {"Technical": {}, "Study": {}, "Metadata": {}}

    # Track keys to avoid duplicates
    seen_keys = set()

    for path in template_paths:
        if not os.path.exists(path):
            print(f"Warning: File not found: {path}")
            continue

        print(f"Merging {path}...")
        with open(path, "r") as f:
            data = json.load(f)

        # Merge top-level keys (Questions)
        for key, value in data.items():
            if key in ["Technical", "Study", "Metadata", "Categories", "TaskName"]:
                continue

            if key in seen_keys:
                print(f"  Warning: Duplicate key '{key}' found in {path}. Overwriting.")

            combined_data[key] = value
            seen_keys.add(key)

        # Merge Metadata (Take the first one, or merge intelligently?)
        # For now, we'll just take the Technical/Study from the first one,
        # but maybe update TaskName if it's a list
        if not combined_data["Technical"]:
            combined_data["Technical"] = data.get("Technical", {})
            combined_data["Study"] = data.get("Study", {})
            combined_data["Metadata"] = data.get("Metadata", {})

            # Update TaskName to be a combination?
            task_name = data.get("TaskName", "")
            if task_name:
                combined_data["TaskName"] = task_name
        else:
            # Append TaskName
            current_name = combined_data.get("TaskName", "")
            new_name = data.get("TaskName", "")
            if new_name and new_name not in current_name:
                combined_data["TaskName"] = f"{current_name}_{new_name}"

    # Final cleanup
    combined_data["Metadata"]["CreationDate"] = date.today().isoformat()
    combined_data["Metadata"]["Creator"] = "Prism Survey Combiner"

    # Save
    with open(output_path, "w") as f:
        json.dump(combined_data, f, indent=2)

    print(f"Successfully created {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combine Prism survey JSON templates.")
    parser.add_argument("--output", "-o", required=True, help="Output JSON filename")
    parser.add_argument(
        "templates", nargs="+", help="List of JSON template files to merge"
    )

    args = parser.parse_args()

    combine_jsons(args.templates, args.output)
