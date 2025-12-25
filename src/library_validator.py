import json
import os
from collections import defaultdict
from pathlib import Path


def check_uniqueness(library_path):
    """
    Validates the library for variable uniqueness and schema compliance.
    Returns True if successful, False if errors were found.
    """
    print(f"Validating library at {library_path}...")

    if not os.path.exists(library_path):
        print(f"Error: Library path {library_path} does not exist.")
        return False

    validator = LibraryValidator(library_path)

    # 1. Check Uniqueness
    print("Checking variable uniqueness...")
    var_map = validator.get_all_library_variables()
    duplicates = {k: v for k, v in var_map.items() if len(v) > 1}

    if not duplicates:
        print("✅ SUCCESS: All variable names are unique across the library.")
    else:
        print(
            f"⚠️  WARNING: Found {len(duplicates)} variable names appearing in multiple files:"
        )
        for var, file_list in duplicates.items():
            print(f"  - '{var}' appears in: {', '.join(file_list)}")

    # 2. Check Schema
    # Note: We don't import load_schema here to avoid circular imports if any.
    # But we can try to import it locally.
    try:
        from .schema_manager import load_schema
        from jsonschema import validate, ValidationError

        print("\nChecking schema compliance...")
        survey_schema = load_schema("survey", version="stable")
        biometrics_schema = load_schema("biometrics", version="stable")

        files = list(Path(library_path).glob("*.json"))
        schema_errors = 0
        for file_path in files:
            if not (
                file_path.name.startswith("survey-")
                or file_path.name.startswith("biometrics-")
            ):
                continue

            schema = (
                survey_schema
                if file_path.name.startswith("survey-")
                else biometrics_schema
            )
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                validate(instance=data, schema=schema)
            except ValidationError as e:
                print(f"❌ Schema error in {file_path.name}: {e.message}")
                schema_errors += 1
            except Exception as e:
                print(f"❌ Error reading {file_path.name}: {e}")
                schema_errors += 1

        if schema_errors == 0:
            print("✅ SUCCESS: All files comply with the PRISM schema.")
        else:
            print(f"❌ FAILURE: Found {schema_errors} schema errors.")
            return False

    except ImportError:
        print("⚠️  Skipping schema check (jsonschema not installed).")

    return True


class LibraryValidator:
    def __init__(self, library_path):
        self.library_path = Path(library_path)
        self.IGNORE_KEYS = {"Technical", "Study", "Metadata", "Questions", "I18n", "Scoring", "Normative"}

    def get_all_library_variables(self, exclude_file=None):
        """
        Returns a map of variable -> list of filenames for the entire library,
        optionally excluding a specific filename (useful when checking a draft against others).
        """
        var_map = defaultdict(list)

        if not self.library_path.exists():
            return var_map

        # Look for both survey and biometrics files
        files = [
            f
            for f in self.library_path.glob("*.json")
            if (f.name.startswith("survey-") or f.name.startswith("biometrics-")) and f.name != exclude_file
        ]

        for file_path in files:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)

                # Handle both flat structure and nested "Questions" structure
                variables = []
                if "Questions" in data and isinstance(data["Questions"], dict):
                    variables = list(data["Questions"].keys())
                else:
                    variables = [k for k in data.keys() if k not in self.IGNORE_KEYS]

                for var in variables:
                    var_map[var].append(file_path.name)

            except Exception as e:
                print(f"Error reading {file_path.name}: {e}")

        return var_map

    def validate_draft(self, draft_content, filename):
        """
        Checks if the draft content introduces any duplicates against the existing library.
        Returns a list of error messages. Empty list means valid.
        """
        errors = []

        # 1. Extract variables from draft
        draft_vars = []
        if "Questions" in draft_content and isinstance(
            draft_content["Questions"], dict
        ):
            draft_vars = list(draft_content["Questions"].keys())
        else:
            draft_vars = [k for k in draft_content.keys() if k not in self.IGNORE_KEYS]

        # 2. Check for internal duplicates (if list? keys are unique in dict, but maybe case sensitivity?)
        # JSON keys are unique by definition in Python dicts, so we are good there.

        # 3. Check against other files
        existing_vars = self.get_all_library_variables(exclude_file=filename)

        for var in draft_vars:
            if var in existing_vars:
                conflicting_files = ", ".join(existing_vars[var])
                errors.append(
                    f"Variable '{var}' is already defined in: {conflicting_files}"
                )

        return errors
