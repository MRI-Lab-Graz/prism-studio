import os
import sys
from pathlib import Path

# Add project root to path to import from src
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.library_validator import LibraryValidator
except ImportError:
    # Fallback for different execution contexts
    sys.path.append(os.path.join(os.getcwd(), "src"))
    from library_validator import LibraryValidator


def check_uniqueness(library_path):
    print(f"Checking uniqueness of variables in {library_path}...")

    if not os.path.exists(library_path):
        print(f"Error: Library path {library_path} does not exist.")
        return False

    validator = LibraryValidator(library_path)
    var_map = validator.get_all_library_variables()

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

    success = check_uniqueness(library_dir)
    sys.exit(0 if success else 1)
