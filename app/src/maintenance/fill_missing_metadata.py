#!/usr/bin/env python3
"""
Fill Missing Metadata Script
----------------------------
Compares PRISM JSON files against their schemas and adds missing keys with empty values.
This helps users see what additional metadata can be provided.

Usage:
    python scripts/fill_missing_metadata.py --modality survey --version stable --path library/survey
    python scripts/fill_missing_metadata.py --modality biometrics --version stable --path library/biometrics
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.schema_manager import load_schema


def get_default_value(prop_schema):
    """Return a default empty value based on the property type"""
    prop_type = prop_schema.get("type")

    if isinstance(prop_type, list):
        # If multiple types, prefer string or object
        if "string" in prop_type:
            return ""
        if "object" in prop_type:
            return {}
        if "array" in prop_type:
            return []
        return None

    if prop_type == "string":
        return ""
    elif prop_type == "object":
        return {}
    elif prop_type == "array":
        return []
    elif prop_type == "integer" or prop_type == "number":
        return None
    elif prop_type == "boolean":
        return False

    return ""


def fill_missing_keys(data, schema_props):
    """Recursively fill missing keys in data based on schema properties"""
    if not isinstance(data, dict):
        return data

    for prop_name, prop_schema in schema_props.items():
        if prop_name.startswith("_"):  # Skip internal validator info
            continue

        if prop_name not in data:
            data[prop_name] = get_default_value(prop_schema)

        # If it's an object and has nested properties, recurse
        if prop_schema.get("type") == "object" and "properties" in prop_schema:
            if not isinstance(data[prop_name], dict):
                data[prop_name] = {}
            fill_missing_keys(data[prop_name], prop_schema["properties"])

    return data


def process_file(file_path, schema):
    """Process a single JSON file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Fill top-level sections defined in schema
        if "properties" in schema:
            data = fill_missing_keys(data, schema["properties"])

        # Handle items/metrics (additionalProperties)
        if "additionalProperties" in schema and isinstance(
            schema["additionalProperties"], dict
        ):
            item_schema = schema["additionalProperties"]
            if "properties" in item_schema:
                reserved = [
                    "Technical",
                    "Study",
                    "Metadata",
                    "I18n",
                    "Scoring",
                    "Normative",
                    "Questions",
                ]
                for key in data:
                    if key not in reserved and isinstance(data[key], dict):
                        fill_missing_keys(data[key], item_schema["properties"])

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Updated: {file_path}")
        return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Fill missing metadata keys from schema"
    )
    parser.add_argument(
        "--modality", required=True, help="Modality (survey, biometrics, etc.)"
    )
    parser.add_argument(
        "--version", default="stable", help="Schema version (default: stable)"
    )
    parser.add_argument("--path", required=True, help="Path to JSON file or directory")

    args = parser.parse_args()

    schema = load_schema(args.modality, version=args.version)
    if not schema:
        print(
            f"Error: Could not load schema for {args.modality} (version: {args.version})"
        )
        sys.exit(1)

    target_path = Path(args.path)
    if target_path.is_file():
        process_file(target_path, schema)
    elif target_path.is_dir():
        for json_file in target_path.glob("*.json"):
            process_file(json_file, schema)
    else:
        print(f"Error: Path {args.path} not found")
        sys.exit(1)


if __name__ == "__main__":
    main()
