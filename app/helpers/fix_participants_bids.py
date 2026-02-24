#!/usr/bin/env python3
"""
Fix common BIDS issues in participants.tsv files.

Fixes:
1. Numeric columns stored as strings (age, etc.)
2. Sex/gender coded as numbers instead of M/F/O
"""

import pandas as pd
from pathlib import Path
import argparse
import sys


def fix_participants_tsv(
    tsv_path: str | Path,
    output_path: str | Path = None,
    sex_mapping: dict = None,
    dry_run: bool = False,
):
    """
    Fix BIDS compliance issues in participants.tsv.

    Args:
        tsv_path: Path to participants.tsv file
        output_path: Path to write fixed file (default: overwrites input)
        sex_mapping: Dict mapping numeric codes to M/F/O (e.g., {1: 'M', 2: 'F'})
        dry_run: If True, only report what would be changed

    Returns:
        (success: bool, message: str, changes: dict)
    """
    tsv_path = Path(tsv_path)
    if not tsv_path.exists():
        return False, f"File not found: {tsv_path}", {}

    if output_path is None:
        output_path = tsv_path
    else:
        output_path = Path(output_path)

    # Default sex mapping (1=M, 2=F, 3=O)
    if sex_mapping is None:
        sex_mapping = {1: "M", 2: "F", 3: "O", "1": "M", "2": "F", "3": "O"}

    try:
        # Read TSV
        df = pd.read_csv(tsv_path, sep="\t", dtype=str)
        original_df = df.copy()
        changes = {}

        print(f"📄 Processing {tsv_path.name} ({len(df)} rows)")
        print(f"   Columns: {', '.join(df.columns.tolist())}\n")

        # Fix 1: Convert age and other numeric columns
        numeric_columns = ["age", "height", "weight", "years_of_education"]
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in numeric_columns:
                try:
                    numeric_values = pd.to_numeric(df[col], errors="coerce")
                    non_null = df[col].notna().sum()
                    numeric_count = numeric_values.notna().sum()

                    if numeric_count > 0:
                        # Check if values changed
                        original_sample = df[col].dropna().head(3).tolist()
                        df[col] = numeric_values
                        new_sample = df[col].dropna().head(3).tolist()

                        if str(original_sample) != str(new_sample):
                            changes[col] = {
                                "type": "numeric_conversion",
                                "before": original_sample,
                                "after": new_sample,
                                "count": numeric_count,
                            }
                            print(
                                f"✓ Fixed '{col}': converted {numeric_count} values from strings to numbers"
                            )
                            print(f"  Example: {original_sample} → {new_sample}")
                except Exception as e:
                    print(f"⚠ Could not convert '{col}': {e}")

        # Fix 2: Convert sex column from numeric codes to M/F/O
        sex_col = None
        for col in df.columns:
            if col.lower() in ["sex", "gender"]:
                sex_col = col
                break

        if sex_col:
            # Check if values are numeric codes
            unique_values = df[sex_col].dropna().unique()
            print(f"\n🔍 Checking '{sex_col}' column...")
            print(f"   Current values: {unique_values.tolist()}")

            # Try to detect if numeric codes
            is_numeric_coded = all(
                str(v).strip() in ["1", "2", "3", "0"] or pd.isna(v)
                for v in df[sex_col]
            )

            if is_numeric_coded:
                original_values = df[sex_col].copy()

                # Convert values using both string and int key lookup for robustness
                def convert_sex_code(x):
                    if pd.isna(x):
                        return x
                    # Try both string and int lookup
                    str_key = str(x).strip()
                    if str_key in sex_mapping:
                        return sex_mapping[str_key]
                    try:
                        int_key = int(x)
                        if int_key in sex_mapping:
                            return sex_mapping[int_key]
                    except (ValueError, TypeError):
                        pass
                    return x  # Return original if no mapping found

                df[sex_col] = df[sex_col].map(convert_sex_code)

                # Check what changed
                before_counts = original_values.value_counts().to_dict()
                after_counts = df[sex_col].value_counts().to_dict()

                changes[sex_col] = {
                    "type": "sex_code_conversion",
                    "mapping": sex_mapping,
                    "before": before_counts,
                    "after": after_counts,
                }

                print(f"✓ Fixed '{sex_col}': converted numeric codes to M/F/O")
                print(f"  Mapping used: {sex_mapping}")
                print(f"  Before: {before_counts}")
                print(f"  After: {after_counts}")
            else:
                print(f"✓ '{sex_col}' already uses BIDS format (M/F/O)")

        if not changes:
            print("\n✓ No changes needed - file is BIDS compliant!")
            return True, "File already compliant", {}

        # Summary
        print(f"\n📊 Summary: Fixed {len(changes)} issues")

        if dry_run:
            print(f"\n[DRY RUN] Would write to: {output_path}")
            return True, f"Would fix {len(changes)} issues", changes

        # Write fixed TSV with no quoting to ensure numeric values stay unquoted
        import csv

        df.to_csv(
            output_path,
            sep="\t",
            index=False,
            na_rep="n/a",
            quoting=csv.QUOTE_NONE,
            escapechar="\\",
        )
        print(f"\n💾 Saved to: {output_path}")

        message = f"Fixed {len(changes)} issues in {tsv_path.name}"
        return True, message, changes

    except Exception as e:
        return False, f"Error: {e}", {}


def main():
    parser = argparse.ArgumentParser(
        description="Fix BIDS compliance issues in participants.tsv (age as string, sex as number)"
    )
    parser.add_argument("tsv_file", help="Path to participants.tsv file")
    parser.add_argument(
        "-o", "--output", help="Output path (default: overwrites input)"
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true", help="Show changes without modifying"
    )
    parser.add_argument(
        "--sex-mapping",
        help='Sex code mapping as JSON, e.g., \'{"1": "M", "2": "F", "3": "O"}\'',
        default=None,
    )

    args = parser.parse_args()

    # Parse sex mapping if provided
    sex_mapping = None
    if args.sex_mapping:
        import json

        sex_mapping = json.loads(args.sex_mapping)

    success, message, changes = fix_participants_tsv(
        args.tsv_file, args.output, sex_mapping, args.dry_run
    )

    print(f"\n{'✓' if success else '✗'} {message}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
