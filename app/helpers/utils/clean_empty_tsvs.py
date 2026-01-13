import os
import csv
import argparse
import sys


def is_file_empty_of_data(filepath):
    """
    Check if a TSV file is effectively empty of data.
    Returns True if:
    - File is empty
    - File has only a header
    - File has a header and the first data row contains only empty values
    """
    try:
        # Check if file is empty (0 bytes)
        if os.path.getsize(filepath) == 0:
            return True

        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")

            try:
                _ = next(reader)
            except StopIteration:
                return True  # Empty file

            try:
                first_row = next(reader)
                # Check if all fields in the first row are empty strings
                # This handles "val1\tval2" -> ["val1", "val2"]
                # And "\t" -> ["", ""]
                if all(field.strip() == "" for field in first_row):
                    return True
                return False  # Has data
            except StopIteration:
                return True  # Only header

    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False


def clean_empty_tsvs(root_dir, dry_run=True):
    print(f"Scanning {root_dir} for empty TSV files...")
    if dry_run:
        print("DRY RUN: No files will be deleted. Use --delete to perform deletion.")

    count = 0
    deleted_count = 0
    deleted_dirs_count = 0

    # Use topdown=False to process subdirectories before parents
    for root, dirs, files in os.walk(root_dir, topdown=False):
        # 1. Process files in current directory
        for file in files:
            if file.endswith(".tsv"):
                filepath = os.path.join(root, file)
                if is_file_empty_of_data(filepath):
                    count += 1
                    if dry_run:
                        print(f"[WOULD DELETE] {filepath}")
                        # Check sidecar for dry run reporting
                        json_path = filepath.replace(".tsv", ".json")
                        if os.path.exists(json_path):
                            print(f"[WOULD DELETE] {json_path} (sidecar)")
                    else:
                        try:
                            os.remove(filepath)
                            print(f"[DELETED] {filepath}")
                            deleted_count += 1

                            # Also check for corresponding JSON sidecar
                            json_path = filepath.replace(".tsv", ".json")
                            if os.path.exists(json_path):
                                os.remove(json_path)
                                print(f"[DELETED] {json_path} (sidecar)")

                        except OSError as e:
                            print(f"Error deleting {filepath}: {e}")

        # 2. Check if directory is empty (after potential file deletions)
        try:
            if not os.path.exists(root):
                continue

            items = os.listdir(root)
            # Filter out system files for the check
            system_files = {".DS_Store", "Thumbs.db"}
            remaining_items = [i for i in items if i not in system_files]

            if not remaining_items:
                # It is effectively empty (only system files or truly empty)
                if dry_run:
                    print(f"[WOULD DELETE DIR] {root}")
                else:
                    # If there are system files, we need to delete them first
                    for item in items:
                        os.remove(os.path.join(root, item))

                    # Now delete the directory
                    # Do not delete the root argument itself
                    if os.path.abspath(root) != os.path.abspath(root_dir):
                        os.rmdir(root)
                        print(f"[DELETED DIR] {root}")
                        deleted_dirs_count += 1
        except OSError as e:
            print(f"Error checking/deleting directory {root}: {e}")

    if dry_run:
        print(f"\nFound {count} empty TSV files.")
    else:
        print(
            f"\nDeleted {deleted_count} empty TSV files and {deleted_dirs_count} empty directories."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Delete TSV files that contain no data (only header or empty rows)."
    )
    parser.add_argument("root_dir", help="Root directory to scan")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete files (default is dry-run)",
    )

    args = parser.parse_args()

    if not os.path.isdir(args.root_dir):
        print(f"Error: {args.root_dir} is not a directory")
        sys.exit(1)

    clean_empty_tsvs(args.root_dir, dry_run=not args.delete)
