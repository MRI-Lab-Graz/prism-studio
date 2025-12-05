import os
import sys
from pathlib import Path
import argparse

# Add current directory to sys.path to import convert_varioport
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from convert_varioport import convert_varioport


def batch_convert(sourcedata_root, base_freq=None):
    # Find all .RAW and .vpd files
    files = []
    for ext in ["*.RAW", "*.vpd"]:
        files.extend(Path(sourcedata_root).rglob(ext))

    print(f"Found {len(files)} files to convert.")

    for file_path in files:
        print(f"Processing {file_path}...")

        # Determine output filenames
        # Input: .../sourcedata/sub-1293167/ses-02/physio/sub-1293167_ses-02_varioport.vpd
        # Output: .../sub-1293167/ses-02/physio/sub-1293167_ses-02_task-rest_recording-vpd_physio.tsv.gz

        # Calculate relative path from sourcedata_root
        try:
            rel_path = file_path.parent.relative_to(sourcedata_root)
        except ValueError:
            # Fallback if file is not relative to sourcedata_root (shouldn't happen with rglob)
            print(f"Skipping {file_path}: Not inside {sourcedata_root}")
            continue

        # Output root is the parent of sourcedata_root (assuming sourcedata_root is .../sourcedata)
        output_root = Path(sourcedata_root).parent

        output_dir = output_root / rel_path
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = file_path.name

        # Parse entities from filename (assuming sub-XXX_ses-YY_...)
        parts = filename.split("_")
        sub = next((p for p in parts if p.startswith("sub-")), None)
        ses = next((p for p in parts if p.startswith("ses-")), None)

        if not sub or not ses:
            print(f"Skipping {filename}: Could not parse sub/ses entities.")
            continue

        # Determine recording label based on extension
        ext = file_path.suffix.lower()
        if ext == ".vpd":
            rec = "vpd"
        elif ext == ".raw":
            rec = "raw"
        else:
            rec = "unknown"

        # Construct BIDS filename
        # sub-XXX_ses-YY_task-rest_recording-ZZZ_physio
        bids_name = f"{sub}_{ses}_task-rest_recording-{rec}_physio"

        output_tsv = output_dir / (bids_name + ".tsv.gz")
        output_json = output_dir / (bids_name + ".json")

        # Skip if already exists? No, overwrite.

        try:
            convert_varioport(
                str(file_path), str(output_tsv), str(output_json), task_name="rest", base_freq=base_freq
            )
        except Exception as e:
            print(f"Error converting {file_path}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sourcedata",
        default="/Volumes/Evo/data/prism_output/sourcedata",
        help="Path to sourcedata root",
    )
    parser.add_argument("--base-freq", type=float, help="Override base frequency (e.g. 1000)")
    args = parser.parse_args()

    batch_convert(args.sourcedata, base_freq=args.base_freq)
