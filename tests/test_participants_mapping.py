#!/usr/bin/env python3
"""
Test script for participants mapping converter.

Usage:
    python tests/test_participants_mapping.py
"""

import sys
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

    # Test 1: Load mapping from code/library
    print("📋 Test 1: Loading participants_mapping.json from code/library/...")
    mapping_file = dataset_root / "code" / "library" / "participants_mapping.json"

    converter = ParticipantsConverter(dataset_path)
    mapping = converter.load_mapping_from_file(mapping_file)

    if mapping:
        print(f"✓ Successfully loaded mapping (version {mapping.get('version')})")
        print(f"  Description: {mapping.get('description')}")
        print(f"  Mappings defined: {list(mapping.get('mappings', {}).keys())}")
    else:
        print("✗ Failed to load mapping")
        return False
    print()

    if mapping:
        print(f"✓ Successfully loaded mapping (version {mapping.get('version')})")
        print(f"  Description: {mapping.get('description')}")
        print(f"  Mappings defined: {list(mapping.get('mappings', {}).keys())}")
    else:
        print("✗ Failed to load mapping")
        return False
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
        return False
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
        return False

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
        print(
            f"  Sex values: {df_verify['sex'].unique().tolist() if 'sex' in df_verify.columns else 'N/A'}"
        )
        print(
            f"  Handedness values: {df_verify['handedness'].unique().tolist() if 'handedness' in df_verify.columns else 'N/A'}"
        )
    else:
        print(f"✗ Output file not created: {output_path}")
        return False
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
    return True


if __name__ == "__main__":
    try:
        success = test_converter()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
