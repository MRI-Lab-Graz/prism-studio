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

    print("\nChecking for redundant item definitions...")
    redundant_issues = validator.find_redundant_items()
    if redundant_issues:
        warning_issues = [i for i in redundant_issues if i["severity"] == "warning"]
        info_issues = [i for i in redundant_issues if i["severity"] == "info"]

        if warning_issues:
            print(f"⚠️  WARNING: Found {len(warning_issues)} redundant item groups:")
            for issue in warning_issues:
                print(f"  - {issue['message']}")
        if info_issues:
            print(f"ℹ️  Info: {len(info_issues)} alias clusters detected:")
            for issue in info_issues:
                print(f"  - {issue['message']}")
    else:
        print("✅ No redundant item definitions detected.")

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

    def _template_files(self, exclude_file=None):
        if not self.library_path.exists():
            return []

        return [
            f
            for f in sorted(self.library_path.glob("*.json"))
            if (f.name.startswith("survey-") or f.name.startswith("biometrics-"))
            and f.name != exclude_file
        ]

    def _iter_template_items(self, file_path):
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        if "Questions" in data and isinstance(data["Questions"], dict):
            items = data["Questions"]
        elif isinstance(data, dict):
            items = {k: v for k, v in data.items() if k not in self.IGNORE_KEYS}
        else:
            return

        for item_id, item_def in items.items():
            yield item_id, item_def

    def _item_signature(self, item_def):
        # Items are considered identical if they share the same content,
        # ignoring both "AliasOf" (backward pointer) and "Aliases" (forward list)
        normalized = {k: item_def[k] for k in sorted(item_def) if k not in ("AliasOf", "Aliases")}
        return json.dumps(normalized, sort_keys=True, ensure_ascii=False)

    def find_redundant_items(self):
        issues = []
        for file_path in self._template_files():
            signature_map = defaultdict(list)
            for item_id, item_def in self._iter_template_items(file_path):
                if not isinstance(item_def, dict):
                    continue
                signature = self._item_signature(item_def)
                signature_map[signature].append((item_id, item_def))

            for group in signature_map.values():
                if len(group) <= 1:
                    continue

                canonical = [item_id for item_id, item_def in group if "AliasOf" not in item_def]
                alias_entries = [
                    (item_id, item_def.get("AliasOf"))
                    for item_id, item_def in group
                    if "AliasOf" in item_def
                ]
                sorted_items = sorted(item_id for item_id, _ in group)

                if alias_entries and len(canonical) == 1 and all(
                    alias_target == canonical[0] for _, alias_target in alias_entries
                ):
                    severity = "info"
                    alias_names = ", ".join(item for item, _ in alias_entries)
                    message = f"{file_path.name}: canonical '{canonical[0]}' has aliases ({alias_names}) that duplicate its content."
                else:
                    severity = "warning"
                    message = (
                        f"{file_path.name}: items {', '.join(sorted_items)} share identical content; remove duplicates or mark them with AliasOf."
                    )

                issues.append(
                    {
                        "file": file_path.name,
                        "items": sorted_items,
                        "canonical": canonical,
                        "aliases": alias_entries,
                        "severity": severity,
                        "message": message,
                    }
                )

        return issues

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
