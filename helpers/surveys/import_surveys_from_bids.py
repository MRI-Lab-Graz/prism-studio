#!/usr/bin/env python3
"""
Import BIDS behavioral sidecars and convert them to Prism survey templates.
"""

import os
import json
import glob
from datetime import date


def import_surveys(bids_root, output_dir):
    """
    Import *_beh.json files from BIDS root and save as Prism templates.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Find all task-*.json files in the root (BIDS inheritance)
    # Also look for them in sub-*/beh/ if not in root (though root is best practice for shared)
    search_pattern = os.path.join(bids_root, "task-*_beh.json")
    files = glob.glob(search_pattern)

    if not files:
        print(f"No task-*_beh.json files found in {bids_root}")
        return

    print(f"Found {len(files)} survey sidecars.")

    for file_path in files:
        filename = os.path.basename(file_path)
        task_name = filename.replace("task-", "").replace("_beh.json", "")

        print(f"Processing {filename}...")

        with open(file_path, "r") as f:
            bids_data = json.load(f)

        # Create Prism structure
        prism_data = {
            # Preserve original BIDS column definitions
            **bids_data,
            # Add required Prism sections
            "Technical": {
                "StimulusType": "Behavior",
                "FileFormat": "tsv",
                "ResponseType": ["keypress"],  # Default, user should edit
                "SoftwarePlatform": "custom",  # Default
            },
            "Study": {
                "Task": task_name,
                "Subject": "sub-001",  # Placeholder
                "Run": "run-01",  # Placeholder
                "TaskType": "reaction_time",  # Default
                "TrialStructure": {"TrialCount": 1},
            },
            "Metadata": {
                "SchemaVersion": "1.1.1",
                "CreationDate": date.today().isoformat(),
                "Creator": "Prism Importer",
            },
        }

        # Save as template
        output_filename = filename  # Keep original name or change to .json
        output_path = os.path.join(output_dir, output_filename)

        with open(output_path, "w") as f:
            json.dump(prism_data, f, indent=2)

        print(f"  -> Saved template to {output_path}")


if __name__ == "__main__":
    # Default paths
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    rawdata_path = os.path.join(workspace_root, "rawdata")
    templates_path = os.path.join(workspace_root, "templates", "surveys")

    import_surveys(rawdata_path, templates_path)
