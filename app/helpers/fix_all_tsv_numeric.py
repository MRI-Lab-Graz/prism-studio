#!/usr/bin/env python3
"""
Batch fix all TSV files in a dataset to ensure numeric columns are stored
as numbers (not strings) to pass BIDS validation.
"""

import pandas as pd
from pathlib import Path
import argparse
import sys
import csv


def fix_tsv_file(tsv_path: Path, dry_run: bool = False):
    """
    Fix numeric columns in a single TSV file.
    
    Returns:
        (fixed: bool, changes: list, error: str or None)
    """
    try:
        # Read TSV
        df = pd.read_csv(tsv_path, sep="\t", dtype=str)
        original_df = df.copy()
        changes = []
        
        # Try to convert ALL columns to numeric if possible
        for col in df.columns:
            # Skip participant_id and other identifier columns
            if col.lower() in ['participant_id', 'sub_id', 'subject_id']:
                continue
            
            # Skip string-only columns (sex, gender, handedness, etc.)
            if col.lower() in ['sex', 'gender', 'handedness', 'group', 'condition']:
                continue
            
            try:
                # Try to convert to numeric
                numeric_values = pd.to_numeric(df[col], errors='coerce')
                numeric_count = numeric_values.notna().sum()
                total_count = df[col].notna().sum()
                
                # Only convert if >80% of values are numeric
                if numeric_count > 0 and (numeric_count / max(total_count, 1)) > 0.8:
                    original_sample = df[col].dropna().head(2).tolist()
                    df[col] = numeric_values
                    new_sample = df[col].dropna().head(2).tolist()
                    
                    if str(original_sample) != str(new_sample):
                        changes.append({
                            'column': col,
                            'converted': numeric_count,
                            'before': original_sample,
                            'after': new_sample
                        })
            except Exception:
                pass
        
        if not changes:
            return False, [], None
        
        if dry_run:
            return True, changes, None
        
        # Write fixed TSV with no quoting
        df.to_csv(tsv_path, sep="\t", index=False, na_rep='n/a', quoting=csv.QUOTE_NONE, escapechar='\\')
        return True, changes, None
        
    except Exception as e:
        return False, [], str(e)


def fix_all_tsvs(dataset_path: str | Path, dry_run: bool = False):
    """
    Find and fix all TSV files in a dataset.
    
    Args:
        dataset_path: Path to BIDS dataset root
        dry_run: If True, only report what would be changed
    """
    dataset_path = Path(dataset_path).expanduser().resolve()
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return False
    
    # Find all TSV files (exclude derivatives and hidden files)
    tsv_files = []
    for tsv_file in dataset_path.rglob("*.tsv"):
        # Skip derivatives and hidden directories
        parts = tsv_file.relative_to(dataset_path).parts
        if any(p.startswith('.') or p == 'derivatives' for p in parts):
            continue
        tsv_files.append(tsv_file)
    
    if not tsv_files:
        print("❌ No TSV files found in dataset")
        return False
    
    print(f"📄 Found {len(tsv_files)} TSV files\n")
    
    fixed_count = 0
    error_count = 0
    total_changes = 0
    
    for tsv_file in sorted(tsv_files):
        rel_path = tsv_file.relative_to(dataset_path)
        fixed, changes, error = fix_tsv_file(tsv_file, dry_run)
        
        if error:
            print(f"❌ {rel_path}: {error}")
            error_count += 1
        elif fixed:
            print(f"✓ {rel_path}")
            for change in changes:
                print(f"  • {change['column']}: {change['before'][:2]} → {change['after'][:2]} ({change['converted']} values)")
            fixed_count += 1
            total_changes += len(changes)
        else:
            # No changes needed - skip output
            pass
    
    print(f"\n{'=' * 60}")
    print(f"📊 Summary:")
    print(f"   Total files: {len(tsv_files)}")
    print(f"   Fixed: {fixed_count} files")
    print(f"   Errors: {error_count} files")
    print(f"   Total columns fixed: {total_changes}")
    
    if dry_run:
        print(f"\n[DRY RUN] No files were modified")
    else:
        print(f"\n💾 All changes saved")
    
    return fixed_count > 0 or error_count == 0


def main():
    parser = argparse.ArgumentParser(
        description="Batch fix all TSV files in a BIDS dataset to ensure numeric columns are stored as numbers"
    )
    parser.add_argument('dataset_path', help='Path to BIDS dataset root')
    parser.add_argument('-n', '--dry-run', action='store_true', help='Show changes without modifying')
    
    args = parser.parse_args()
    
    success = fix_all_tsvs(args.dataset_path, args.dry_run)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
