#!/usr/bin/env python3
"""
Test script to verify SPSS .sav file anonymization with existing mapping.

Usage:
    python test_sav_anonymization.py <dataset_path> [sav_filename]
"""

import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import pyreadstat


def test_sav_anonymization(dataset_path: str, sav_filename: str = "recipe-maia.sav"):
    """Test anonymization on a single .sav file.

    Args:
        dataset_path: Path to the dataset root directory
        sav_filename: Name of the .sav file to test (default: recipe-maia.sav)
    """

    # Paths
    dataset = Path(dataset_path)
    derivatives = dataset / "derivatives" / "survey"
    mapping_file = derivatives / "participants_mapping.json"
    sav_file = derivatives / "recipe-maia.sav"

    if not mapping_file.exists():
        print(f"❌ Mapping file not found: {mapping_file}")
        return False

    if not sav_file.exists():
        print(f"❌ SPSS file not found: {sav_file}")
        return False

    # Load mapping
    print(f"Loading mapping from: {mapping_file}")
    with open(mapping_file, "r") as f:
        mapping_data = json.load(f)
        participant_mapping = mapping_data.get("mapping", {})

    print(f"✓ Loaded {len(participant_mapping)} ID mappings")
    print("\nSample mappings:")
    for i, (orig, anon) in enumerate(list(participant_mapping.items())[:3]):
        print(f"  {orig} → {anon}")

    # Read SPSS file
    print(f"\nReading SPSS file: {sav_file.name}")
    df, meta = pyreadstat.read_sav(str(sav_file))

    print(f"✓ Loaded {len(df)} rows, {len(df.columns)} columns")

    if "participant_id" not in df.columns:
        print("❌ No participant_id column found")
        print(f"   Available columns: {', '.join(df.columns[:10])}")
        return False

    # Show original IDs
    original_ids = df["participant_id"].unique()
    print(f"\nOriginal IDs (first 5): {sorted(original_ids)[:5]}")

    # Apply mapping
    df["participant_id"] = df["participant_id"].map(
        lambda x: participant_mapping.get(x, x)
    )

    # Show anonymized IDs
    anonymized_ids = df["participant_id"].unique()
    print(f"Anonymized IDs (first 5): {sorted(anonymized_ids)[:5]}")

    # Check if actually anonymized
    still_original = [pid for pid in anonymized_ids if pid.startswith("sub-0")]
    if still_original:
        print(f"\n⚠️  WARNING: {len(still_original)} IDs still look original:")
        print(f"   {still_original[:5]}")
    else:
        print(f"\n✓ All {len(anonymized_ids)} IDs successfully anonymized!")

    # Write back (to a test file, not overwrite original)
    test_output = derivatives / "test_anonymized.sav"
    print(f"\nWriting test output to: {test_output.name}")
    pyreadstat.write_sav(
        df, str(test_output), column_labels=meta.column_names_to_labels
    )
    print("✓ Written successfully")

    # Verify by reading back
    df_verify, _ = pyreadstat.read_sav(str(test_output))
    verify_ids = df_verify["participant_id"].unique()
    print(f"\nVerification: Read back {len(verify_ids)} unique IDs")
    print(f"First 3: {sorted(verify_ids)[:3]}")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_sav_anonymization.py <dataset_path> [sav_filename]")
        print(
            "Example: python test_sav_anonymization.py /path/to/Dann_and_Brain recipe-maia.sav"
        )
        sys.exit(1)

    dataset_path = sys.argv[1]
    sav_filename = sys.argv[2] if len(sys.argv) > 2 else "recipe-maia.sav"
    print("=" * 70)
    print("SPSS File Anonymization Test")
    print("=" * 70)
    print()

    try:
        success = test_sav_anonymization(dataset_path, sav_filename)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
