from pathlib import Path


def cleanup_duplicates(root_dir):
    root = Path(root_dir)
    # Find all physio directories
    physio_dirs = root.rglob("physio")

    for physio_dir in physio_dirs:
        if not physio_dir.is_dir():
            continue

        # List all files
        files = list(physio_dir.glob("*"))

        # Group by prefix (sub-XXX_ses-YY_task-rest)
        # We expect files like:
        # sub-XXX_ses-YY_task-rest_recording-raw_physio.tsv.gz
        # sub-XXX_ses-YY_task-rest_recording-vpd_physio.tsv.gz

        # We want to find pairs.
        # Let's look for raw files.
        raw_files = list(physio_dir.glob("*recording-raw_physio.tsv.gz"))

        for raw_file in raw_files:
            # Construct the expected vpd filename
            vpd_file = raw_file.parent / raw_file.name.replace(
                "recording-raw", "recording-vpd"
            )

            if vpd_file.exists():
                print(f"Duplicate found in {physio_dir}:")
                print(f"  Keeping: {vpd_file.name}")
                print(f"  Removing: {raw_file.name}")

                # Remove raw .tsv.gz
                raw_file.unlink()

                # Remove raw .json if it exists
                # raw_file is like ...physio.tsv.gz
                # json is ...physio.json
                raw_json = raw_file.parent / raw_file.name.replace(".tsv.gz", ".json")

                if raw_json.exists():
                    print(f"  Removing: {raw_json.name}")
                    raw_json.unlink()
            else:
                print(f"Unique RAW file found (keeping): {raw_file.name}")


if __name__ == "__main__":
    cleanup_duplicates("/Volumes/Evo/data/prism_output")
