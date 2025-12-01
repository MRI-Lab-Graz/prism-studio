import os
import json
import sys
from collections import defaultdict


def check_uniqueness(library_path):
    print(f"Checking uniqueness of variables in {library_path}...")

    if not os.path.exists(library_path):
        print(f"Error: Library path {library_path} does not exist.")
        return

    # Store where each variable is seen: variable -> [file1, file2]
    var_map = defaultdict(list)

    # Standard keys to ignore
    IGNORE_KEYS = {"Technical", "Study", "Metadata"}

    files = [
        f
        for f in os.listdir(library_path)
        if f.endswith(".json") and f.startswith("survey-")
    ]

    for filename in files:
        filepath = os.path.join(library_path, filename)
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            # Get variables
            variables = [k for k in data.keys() if k not in IGNORE_KEYS]

            for var in variables:
                var_map[var].append(filename)

        except json.JSONDecodeError:
            print(f"Error decoding {filename}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Report duplicates
    duplicates = {k: v for k, v in var_map.items() if len(v) > 1}

    if not duplicates:
        print("\n✅ SUCCESS: All variable names are unique across the library.")
    else:
        print(
            f"\n⚠️  WARNING: Found {len(duplicates)} variable names appearing in multiple files:"
        )
        for var, file_list in duplicates.items():
            print(f"  - '{var}' appears in: {', '.join(file_list)}")

    return len(duplicates) == 0


if __name__ == "__main__":
    library_dir = "survey_library"
    if len(sys.argv) > 1:
        library_dir = sys.argv[1]

    check_uniqueness(library_dir)
