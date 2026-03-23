#!/usr/bin/env python3
"""
Test script for participants mapping converter.

Usage:
    python tests/test_participants_mapping.py
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.participants_converter import ParticipantsConverter


def test_converter():
    """Test the participants converter with the workshop example."""

    # The mapping is now in code/library/
    dataset_root = (
        Path(__file__).parent.parent / "examples" / "workshop" / "exercise_1_raw_data"
    )
    source_file = dataset_root / "raw_data" / "wellbeing.tsv"

    # For the converter test, we'll use the rawdata simulation
    # In a real scenario, this would be the actual rawdata/ folder
    dataset_path = dataset_root / "rawdata"
    dataset_path.mkdir(exist_ok=True)

    print("=" * 70)
    print("Testing Participants Mapping Converter")
    print("=" * 70)
    print()

    # Test 1: Load mapping from dataset root (create fixture if needed)
    print("📋 Test 1: Loading participants_mapping.json from dataset root...")
    mapping_file = dataset_path / "participants_mapping.json"

    if not mapping_file.exists():
        mapping_fixture = {
            "version": "1.0",
            "description": "Workshop fixture mapping for participants conversion test",
            "mappings": {
                "participant_id": {
                    "source_column": "participant_id",
                    "standard_variable": "participant_id",
                    "type": "string",
                },
                "age": {
                    "source_column": "age",
                    "standard_variable": "age",
                    "type": "number",
                },
                "sex": {
                    "source_column": "sex",
                    "standard_variable": "sex",
                    "type": "string",
                    "value_mapping": {"1": "M", "2": "F", "4": "O"},
                },
                "education": {
                    "source_column": "education",
                    "standard_variable": "education",
                    "type": "string",
                },
                "handedness": {
                    "source_column": "handedness",
                    "standard_variable": "handedness",
                    "type": "string",
                    "value_mapping": {"1": "R", "2": "L"},
                },
            },
        }
        mapping_file.write_text(json.dumps(mapping_fixture, indent=2), encoding="utf-8")

    converter = ParticipantsConverter(dataset_path)
    mapping = converter.load_mapping_from_file(mapping_file)

    if mapping:
        print(f"✓ Successfully loaded mapping (version {mapping.get('version')})")
        print(f"  Description: {mapping.get('description')}")
        print(f"  Mappings defined: {list(mapping.get('mappings', {}).keys())}")
    else:
        print("✗ Failed to load mapping")
        assert False, "Failed to load mapping"
    print()

    if mapping:
        print(f"✓ Successfully loaded mapping (version {mapping.get('version')})")
        print(f"  Description: {mapping.get('description')}")
        print(f"  Mappings defined: {list(mapping.get('mappings', {}).keys())}")
    else:
        print("✗ Failed to load mapping")
        assert False, "Failed to load mapping"
    print()

    # Test 2: Validate mapping
    print("📋 Test 2: Validating mapping specification...")
    is_valid, errors = converter.validate_mapping(mapping)

    if is_valid:
        print("✓ Mapping is valid")
    else:
        print("✗ Validation errors:")
        for error in errors:
            print(f"  - {error}")
        assert False, "Mapping validation failed"
    print()

    # Test 3: Convert participant data
    print("📋 Test 3: Converting participant data...")
    success, df, messages = converter.convert_participant_data(
        source_file, mapping, output_file=dataset_path / "participants.tsv"
    )

    print("\nConversion Messages:")
    for msg in messages:
        print(f"  {msg}")

    if not success:
        print("✗ Conversion failed")
        assert False, "Conversion failed"

    print()
    print("📊 Conversion Results:")
    if df is not None:
        print(f"  Rows: {len(df)}")
        print(f"  Columns: {list(df.columns)}")
        print("\n  Sample data (first 3 rows):")
        print(df.head(3).to_string(index=False).replace("\n", "\n    "))
    print()

    # Test 4: Verify output file was created
    print("📋 Test 4: Verifying output file...")
    output_path = dataset_path / "participants.tsv"
    if output_path.exists():
        print(f"✓ Created {output_path.name}")
        # Read back and verify
        import pandas as pd

        df_verify = pd.read_csv(output_path, sep="\t")
        print(f"  Rows in file: {len(df_verify)}")
        sex_values = (
            sorted({str(v) for v in df_verify["sex"].dropna().tolist()})
            if "sex" in df_verify.columns
            else []
        )
        handedness_values = (
            sorted({str(v) for v in df_verify["handedness"].dropna().tolist()})
            if "handedness" in df_verify.columns
            else []
        )

        print(f"  Sex values: {sex_values if sex_values else 'N/A'}")
        print(
            f"  Handedness values: {handedness_values if handedness_values else 'N/A'}"
        )

        # Conversion must preserve source coding (no recoding 1->M/R etc.).
        assert "M" not in sex_values and "F" not in sex_values
        assert "R" not in handedness_values and "L" not in handedness_values
        assert "1" in sex_values and "2" in sex_values
        assert "1" in handedness_values and "2" in handedness_values
    else:
        print(f"✗ Output file not created: {output_path}")
        assert False, "Output file not created"
    print()

    # Test 5: Template generation
    print("📋 Test 5: Testing template generation...")
    success, template, messages = converter.create_mapping_template(
        source_file, output_file=dataset_path / "participants_mapping_template.json"
    )

    print("Template generation messages:")
    for msg in messages:
        print(f"  {msg}")

    if success:
        print(
            f"✓ Template generated with {len(template.get('mappings', {}))} suggested mappings"
        )
    print()

    print("=" * 70)
    print("✓ All tests passed!")
    print("=" * 70)
    return


if __name__ == "__main__":
    try:
        test_converter()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
