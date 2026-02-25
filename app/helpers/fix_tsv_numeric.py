#!/usr/bin/env python3
"""
Fix numeric columns in TSV files (participants.tsv, behavioral data, etc.).

Converts string-type numeric columns to proper numbers, removing quotes
that cause BIDS validation errors.
"""

import pandas as pd
from pathlib import Path
import argparse
import sys
from typing import Optional


def fix_numeric_columns(
    tsv_path: str | Path,
    output_path: Optional[str | Path] = None,
    dry_run: bool = False,
):
    """
    Fix numeric columns in a TSV file.

    Args:
        tsv_path: Path to TSV file to fix
        output_path: Path to write fixed TSV (default: overwrites input)
        dry_run: If True, only report what would be changed

    Returns:
        (success: bool, message: str, fixed_columns: list)
    """
    tsv_path = Path(tsv_path)
    if not tsv_path.exists():
        return False, f"File not found: {tsv_path}", []

    if output_path is None:
        output_path = tsv_path
    else:
        output_path = Path(output_path)

    try:
        # Read TSV
        df = pd.read_csv(tsv_path, sep="\t", dtype=str)  # Read all as strings first
        original_df = df.copy()

        # Columns that should be numeric
        numeric_columns = ["age", "height", "weight", "years_of_education"]
        fixed_columns = []

        for col in df.columns:
            col_lower = col.lower()

            # Check if column should be numeric
            if col_lower in numeric_columns or any(
                keyword in col_lower
                for keyword in [
                    "age",
                    "year",
                    "duration",
                    "score",
                    "response_time",
                    "rt",
                ]
            ):
                try:
                    # Try to convert to numeric
                    numeric_values = pd.to_numeric(df[col], errors="coerce")

                    # Only convert if mostly numeric (>50% valid numbers)
                    non_null_count = df[col].notna().sum()
                    numeric_count = numeric_values.notna().sum()

                    if numeric_count > 0 and (numeric_count / non_null_count) > 0.5:
                        df[col] = numeric_values
                        fixed_columns.append(col)
                        print(
                            f"✓ Fixed '{col}': converted {numeric_count} values to numeric"
                        )
                except Exception as e:
                    print(f"⚠ Skipped '{col}': {e}")

        if not fixed_columns:
            return True, "No numeric columns needed fixing", []

        # Check what changed
        changes = []
        for col in fixed_columns:
            sample_before = original_df[col].dropna().head(3).tolist()
            sample_after = df[col].dropna().head(3).tolist()
            changes.append(f"  {col}: {sample_before} → {sample_after}")

        print(f"\nFixed {len(fixed_columns)} columns:")
        for change in changes:
            print(change)

        if dry_run:
            print(f"\n[DRY RUN] Would write to: {output_path}")
            return True, f"Would fix {len(fixed_columns)} columns", fixed_columns

        # Write fixed TSV
        df.to_csv(output_path, sep="\t", index=False, na_rep="n/a")

        message = f"Fixed {len(fixed_columns)} columns in {tsv_path.name}"
        return True, message, fixed_columns

    except Exception as e:
        return False, f"Error: {e}", []


def main():
    parser = argparse.ArgumentParser(
        description="Fix numeric columns in TSV files (removes quotes from age, etc.)"
    )
    parser.add_argument("tsv_file", help="Path to TSV file to fix")
    parser.add_argument(
        "-o", "--output", help="Output path (default: overwrites input)"
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying",
    )

    args = parser.parse_args()

    success, message, fixed = fix_numeric_columns(
        args.tsv_file, args.output, args.dry_run
    )

    print(f"\n{'✓' if success else '✗'} {message}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
