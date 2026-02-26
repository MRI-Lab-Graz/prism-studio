#!/usr/bin/env python3
"""
Apply anonymization to all SPSS files in derivatives/survey using existing mapping.

Usage:
    python scripts/data/anonymize_sav_files.py <dataset_path>
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import pyreadstat


def anonymize_all_sav_files(dataset_path: str):
    """Anonymize all .save files in derivatives/survey.

    Args:
        dataset_path: Path to the dataset root directory
    """

    # Paths
    dataset = Path(dataset_path)
    derivatives = dataset / "derivatives" / "survey"
    mapping_file = derivatives / "participants_mapping.json"

    if not mapping_file.exists():
        print(f"❌ Mapping file not found: {mapping_file}")
        return False

    # Load mapping
    print(f"Loading mapping from: {mapping_file}")
    with open(mapping_file, "r") as f:
        mapping_data = json.load(f)
        participant_mapping = mapping_data.get("mapping", {})

    print(f"✓ Loaded {len(participant_mapping)} ID mappings\n")

    # Find all .save files
    sav_files = list(derivatives.glob("*.save"))
    if not sav_files:
        print(f"❌ No .save files found in {derivatives}")
        return False

    print(f"Found {len(sav_files)} SPSS files to anonymize:\n")

    anonymized_count = 0
    for sav_file in sorted(sav_files):
        print(f"Processing: {sav_file.name}")

        try:
            # Read SPSS file
            df, meta = pyreadstat.read_sav(str(sav_file))

            if "participant_id" not in df.columns:
                print("  ⚠️  No participant_id column, skipping")
                continue

            # Apply mapping
            original_ids = df["participant_id"].unique()
            df["participant_id"] = df["participant_id"].map(
                lambda x: participant_mapping.get(x, x)
            )
            anonymized_ids = df["participant_id"].unique()

            # Write back
            pyreadstat.write_sav(
                df, str(sav_file), column_labels=meta.column_names_to_labels
            )

            print(f"  ✓ Anonymized {len(original_ids)} unique IDs")
            anonymized_count += 1

        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue

    print(f"\n{'=' * 70}")
    print(f"✓ Successfully anonymized {anonymized_count}/{len(sav_files)} files")
    print(f"{'=' * 70}")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/data/anonymize_sav_files.py <dataset_path>")
        print("Example: python scripts/data/anonymize_sav_files.py /path/to/Dann_and_Brain")
        sys.exit(1)

    dataset_path = sys.argv[1]
    print("=" * 70)
    print("Anonymize All SPSS Files in Dataset")
    print("=" * 70)
    print()

    try:
        success = anonymize_all_sav_files(dataset_path)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
