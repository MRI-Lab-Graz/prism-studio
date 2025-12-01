#!/usr/bin/env python3
"""
Excel to JSON Library Converter
-------------------------------
Converts a data dictionary (Excel) into a library of PRISM-compliant JSON sidecars.

Usage:
    python scripts/excel_to_library.py --excel metadata.xlsx --output survey_library

Excel Format Requirements:
    - Column 1: Variable Name (e.g., ADS1, BDI_1)
    - Column 2: Question/Description (e.g., "I feel sad")
    - Column 3: Scale/Levels (e.g., "1=Not at all; 2=Very much")

The script groups variables into surveys based on their prefix (e.g., ADS1 -> ads).
"""

import pandas as pd
import json
import os
import re
import sys
import argparse

# Standard metadata for known instruments
# You can extend this dictionary or load it from an external file
SURVEY_METADATA = {
    "ads": {
        "OriginalName": "Allgemeine Depressionsskala (ADS)",
        "Citation": "Hautzinger, M., & Bailer, M. (1993). Allgemeine Depressionsskala (ADS). Göttingen: Hogrefe.",
    },
    "bdi": {
        "OriginalName": "Beck Depression Inventory (BDI-II)",
        "Citation": "Beck, A. T., Steer, R. A., & Brown, G. K. (1996). Manual for the Beck Depression Inventory-II. San Antonio, TX: Psychological Corporation.",
    },
    # Add more here...
}


def clean_variable_name(name):
    """Clean variable name to be used as a key."""
    return str(name).strip()


def extract_prefix(var_name):
    """
    Extract prefix from variable name to group surveys.
    Example: ADS1 -> ADS, BDI_1 -> BDI
    """
    match = re.match(r"([a-zA-Z]+)", var_name)
    if match:
        return match.group(1)
    return "unknown"


def parse_levels(scale_str):
    """
    Parse scale string into a dictionary.
    Format expected: "1=Label A; 2=Label B" or "1=Label A, 2=Label B"
    """
    if pd.isna(scale_str):
        return None

    levels = {}
    parts = re.split(r"[;,]\s*", str(scale_str))
    for part in parts:
        if "=" in part:
            val, label = part.split("=", 1)
            levels[val.strip()] = label.strip()
    return levels if levels else None


def process_excel(excel_file, output_dir):
    print(f"Loading metadata from {excel_file}...")
    try:
        # Read header=None to inspect first row
        df_meta = pd.read_excel(excel_file, header=None)

        # Simple heuristic to skip header if present
        first_cell = str(df_meta.iloc[0, 0])
        if "Variable" in first_cell or "Name" in first_cell:
            print("Detected header row, skipping...")
            df_meta = df_meta.iloc[1:]

    except Exception as e:
        print(f"Error reading Excel file: {e}")
        sys.exit(1)

    surveys = {}

    print("Processing metadata...")
    for index, row in df_meta.iterrows():
        var_name = clean_variable_name(row[0])
        question = row[1] if len(row) > 1 else ""
        scale = row[2] if len(row) > 2 else None

        if var_name.lower() == "nan" or not var_name:
            continue

        prefix = extract_prefix(var_name).lower()

        if prefix not in surveys:
            surveys[prefix] = {}

        description = str(question).strip() if pd.notna(question) else var_name
        # Remove brackets [] and their content from description (common in codebooks)
        description = re.sub(r"\[.*?\]", "", description).strip()

        entry = {"Description": description}

        levels = parse_levels(scale)
        if levels:
            entry["Levels"] = levels

        surveys[prefix][var_name] = entry

    # Generate JSON Sidecars
    print(f"Generating JSON sidecars in {output_dir}...")
    os.makedirs(output_dir, exist_ok=True)

    for prefix, variables in surveys.items():
        # Check if this prefix is designated as participants (demographics)
        is_participants = prefix == args.participants_prefix

        # Get metadata if available
        meta = SURVEY_METADATA.get(prefix, {})
        original_name = meta.get("OriginalName", f"{prefix} Questionnaire")
        citation = meta.get("Citation", "")
        domain = meta.get("Domain", "")
        keywords = meta.get("Keywords", [])

        sidecar = {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv",
                "SoftwarePlatform": "Legacy/Imported",
                "Language": "en",  # Default to English, change as needed
                "Respondent": "self",
                "ResponseType": ["paper-pencil"],
            },
            "Study": {
                "TaskName": prefix,
                "OriginalName": original_name,
                "Version": "1.0",
                "Description": f"Imported {prefix} survey data",
            },
            "Metadata": {
                "SchemaVersion": "1.0.0",
                "CreationDate": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "Creator": "excel_to_library.py",
            },
        }

        if citation:
            sidecar["Study"]["Citation"] = citation
        if domain:
            sidecar["Study"]["Domain"] = domain
        if keywords:
            sidecar["Study"]["Keywords"] = keywords

        # Add variables
        sidecar.update(variables)

        if is_participants:
            json_filename = "participants.json"
            # participants.json doesn't strictly need Technical/Study headers in BIDS,
            # but keeping them for PRISM consistency is fine.
            # BIDS apps usually ignore extra keys in participants.json.
        else:
            json_filename = f"survey-{prefix}.json"

        json_path = os.path.join(output_dir, json_filename)
        with open(json_path, "w") as f:
            json.dump(sidecar, f, indent=2)
            print(f"  - Created {json_path}")

    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Excel data dictionary to PRISM JSON library."
    )
    parser.add_argument(
        "--excel", required=True, help="Path to the Excel metadata file."
    )
    parser.add_argument(
        "--output", default="survey_library", help="Output directory for JSON files."
    )
    parser.add_argument(
        "--participants-prefix",
        default=None,
        help="Prefix to treat as participants.json (e.g., 'demo').",
    )

    args = parser.parse_args()
    process_excel(args.excel, args.output)
