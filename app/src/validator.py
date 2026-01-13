"""
Core validation logic for prism
"""

import os
import re
import json
import csv
from pathlib import Path
from datetime import datetime
from jsonschema import validate, ValidationError
from schema_manager import validate_schema_version
from cross_platform import (
    normalize_path,
    safe_path_join,
    CrossPlatformFile,
    validate_filename_cross_platform,
)

# PRISM-specific modalities that we validate with our schemas
# Standard BIDS modalities (anat, func, fmap, dwi, eeg) are passed through
# and should be validated by the optional BIDS validator instead
PRISM_MODALITIES = {"survey", "biometrics", "events", "physio", "physiological", "eyetracking"}

# Standard BIDS modalities - we only do minimal checks (subject/session consistency)
# Full validation is delegated to the BIDS validator
BIDS_MODALITIES = {"anat", "func", "fmap", "dwi", "eeg"}

# Modality patterns (only enforced for PRISM modalities)
MODALITY_PATTERNS = {
    # PRISM survey/biometrics must carry explicit suffixes
    "survey": r".+_survey\.(tsv|json)$",
    "biometrics": r".+_biometrics\.(tsv|json)$",
    "events": r".+_events\.tsv$",
    "physio": r".+(_recording-(ecg|cardiac|puls|resp|eda|ppg|emg|temp|bp|spo2|trigger|[a-zA-Z0-9]+))?_physio\.(tsv|tsv\.gz|json|edf)$",
    "physiological": r".+(_recording-(ecg|cardiac|puls|resp|eda|ppg|emg|temp|bp|spo2|trigger|[a-zA-Z0-9]+))?_physio\.(tsv|tsv\.gz|json|edf)$",
    "eyetracking": r".+(_trackedEye-(left|right|both))?_(eyetrack|eye|gaze)\.(tsv|tsv\.gz|json|edf|asc)$",
}

# BIDS naming patterns
BIDS_REGEX = re.compile(
    r"^sub-[a-zA-Z0-9]+"  # subject
    r"(_ses-[a-zA-Z0-9]+)?"  # optional session
    r"(_[a-zA-Z0-9]+-[a-zA-Z0-9]+)*"  # any number of key-value pairs (task, acq, dir, rec, run, etc.)
    r"(_[a-zA-Z0-9]+)?$"  # generic suffix (e.g., _dwi, _T1w, _bold, _physio, _events)
)

MRI_SUFFIX_REGEX = re.compile(
    r"_(T1w|T2w|T2star|FLAIR|PD|PDw|T1map|T2map|bold|dwi|magnitude1|magnitude2|phasediff|fieldmap|epi|sbref)$"
)

# File extensions that need special handling
COMPOUND_EXTS = (".nii.gz", ".tsv.gz", ".edf.gz")


def split_compound_ext(filename):
    """Return (stem, ext) and handle compound extensions like .nii.gz."""
    if any(filename.endswith(ext) for ext in COMPOUND_EXTS):
        for ext in COMPOUND_EXTS:
            if filename.endswith(ext):
                stem = filename[: -len(ext)]
                return stem, ext
    base, ext = os.path.splitext(filename)
    return base, ext


def derive_sidecar_path(file_path):
    """Derive the JSON sidecar path for a data file."""
    file_path = normalize_path(file_path)
    dirname = os.path.dirname(file_path)
    fname = os.path.basename(file_path)
    stem, _ext = split_compound_ext(fname)
    return safe_path_join(dirname, f"{stem}.json")


def _extract_entity_value(stem, key):
    match = re.search(rf"_{key}-([a-zA-Z0-9]+)", stem)
    if match:
        return match.group(1)
    return None


def resolve_sidecar_path(file_path, root_dir, library_path=None):
    """Return best-matching sidecar path, supporting dataset-level survey sidecars."""
    candidate = derive_sidecar_path(file_path)
    if os.path.exists(candidate):
        return candidate

    stem, _ext = split_compound_ext(os.path.basename(file_path))
    suffix = ""
    if "_" in stem:
        suffix = stem.split("_")[-1]

    survey_value = _extract_entity_value(stem, "survey")
    biometrics_value = _extract_entity_value(stem, "biometrics")
    task_value = _extract_entity_value(stem, "task")

    label_candidates = []
    if survey_value:
        label_candidates.append(("survey", survey_value))
    if biometrics_value:
        label_candidates.append(("biometrics", biometrics_value))
    if task_value:
        label_candidates.append(("task", task_value))
        if not survey_value and not biometrics_value:
            label_candidates.append(("survey", task_value))
            label_candidates.append(("biometrics", task_value))

    search_dirs = [
        root_dir,
        safe_path_join(root_dir, "surveys"),
        safe_path_join(root_dir, "biometrics"),
    ]

    # Add library paths if provided
    if library_path:
        library_root = Path(library_path)
        search_dirs.append(str(library_root))
        search_dirs.append(str(library_root / "survey"))
        search_dirs.append(str(library_root / "biometrics"))

    for prefix, value in label_candidates:
        base_name = f"{prefix}-{value}"
        suffix_part = f"_{suffix}" if suffix and suffix != base_name else ""
        file_name = f"{base_name}{suffix_part}.json"
        for directory in search_dirs:
            if not directory:
                continue
            dataset_candidate = safe_path_join(directory, file_name)
            if os.path.exists(dataset_candidate):
                return dataset_candidate

    return candidate


class DatasetValidator:
    """Main dataset validation class"""

    def __init__(self, schemas=None, library_path=None):
        self.schemas = schemas or {}
        self.library_path = library_path

    def _build_effective_defs(self, sidecar_data: dict) -> dict:
        """Resolve AliasOf and Aliases in sidecar data to build a flat definition table."""
        effective_defs = {}
        # First pass: identify canonical items and their direct aliases
        for k, v in sidecar_data.items():
            if not isinstance(v, dict):
                continue
            effective_defs[k] = v
            if "Aliases" in v and isinstance(v["Aliases"], list):
                for alias in v["Aliases"]:
                    # If the alias column doesn't have its own explicit definition,
                    # point it to this canonical parent.
                    if alias not in sidecar_data:
                        effective_defs[alias] = v

        # Second pass: resolve explicit AliasOf pointers
        for k, v in sidecar_data.items():
            if isinstance(v, dict) and "AliasOf" in v:
                target = v["AliasOf"]
                if target in sidecar_data:
                    effective_defs[k] = sidecar_data[target]
        return effective_defs

    def _get_allowed_values_list(self, col_def: dict) -> list | None:
        """Get the list of allowed values from a column definition, resolving range logic."""
        if "AllowedValues" in col_def and isinstance(col_def["AllowedValues"], list):
            return [str(x) for x in col_def["AllowedValues"]]

        if "Levels" in col_def and isinstance(col_def["Levels"], dict):
            levels = col_def["Levels"]
            level_keys = list(levels.keys())

            # If explicit MinValue/MaxValue are provided, use them to define the range
            min_val = col_def.get("MinValue")
            max_val = col_def.get("MaxValue")

            if min_val is not None and max_val is not None:
                try:
                    min_i = int(float(min_val))
                    max_i = int(float(max_val))
                    return [str(i) for i in range(min_i, max_i + 1)]
                except (ValueError, TypeError):
                    return level_keys

            # Fallback: key range expansion for numeric ordinal scales
            numeric_level_keys = []
            non_numeric_keys = []
            for k in level_keys:
                try:
                    numeric_level_keys.append(int(float(k)))
                except (ValueError, TypeError):
                    non_numeric_keys.append(k)

            if numeric_level_keys:
                min_level, max_level = min(numeric_level_keys), max(numeric_level_keys)
                # Only expand if it looks like a continuous Likert-style range
                # and doesn't create thousands of entries from arbitrary numbers
                if 1 < (max_level - min_level) < 100:
                    full_range = [str(i) for i in range(min_level, max_level + 1)]
                    return full_range + non_numeric_keys

            return level_keys
        return None

    def _check_allowed_values(
        self, value: str, col_name: str, col_def: dict, file_name: str, row_idx: int
    ) -> list:
        """Checks if a value is within the allowed values or levels."""
        allowed = self._get_allowed_values_list(col_def)
        if not allowed or value in allowed:
            return []

        # Try numeric normalization (e.g., "7.0" -> "7")
        try:
            f_val = float(value)
            if f_val.is_integer() and str(int(f_val)) in allowed:
                return []
        except (ValueError, TypeError):
            pass

        return [
            (
                "ERROR",
                f"{file_name} line {row_idx}: Value '{value}' for '{col_name}' is not in allowed values: {allowed}",
            )
        ]

    def _check_data_type(
        self, value: str, col_name: str, col_def: dict, file_name: str, row_idx: int
    ) -> list:
        """Checks if a value matches the expected DataType (integer, float, date)."""
        issues = []
        dtype = col_def.get("DataType")

        # Check Units="date" if DataType is missing
        if not dtype and col_def.get("Units") == "date":
            dtype = "date"

        if not dtype:
            return []

        if dtype == "integer":
            try:
                if not float(value).is_integer():
                    issues.append(
                        (
                            "ERROR",
                            f"{file_name} line {row_idx}: Value '{value}' for '{col_name}' is not a valid integer",
                        )
                    )
            except ValueError:
                issues.append(
                    (
                        "ERROR",
                        f"{file_name} line {row_idx}: Value '{value}' for '{col_name}' is not a valid integer",
                    )
                )
        elif dtype == "float":
            try:
                float(value)
            except ValueError:
                issues.append(
                    (
                        "ERROR",
                        f"{file_name} line {row_idx}: Value '{value}' for '{col_name}' is not a valid float",
                    )
                )
        elif dtype == "date":
            formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]
            valid_date, date_val = False, None
            for fmt in formats:
                try:
                    date_val = datetime.strptime(value, fmt)
                    valid_date = True
                    break
                except ValueError:
                    continue

            if valid_date:
                if date_val > datetime.now():
                    issues.append(
                        (
                            "WARNING",
                            f"{file_name} line {row_idx}: Date '{value}' for '{col_name}' is in the future",
                        )
                    )
                if date_val.year < 1900:
                    issues.append(
                        (
                            "WARNING",
                            f"{file_name} line {row_idx}: Date '{value}' for '{col_name}' is before 1900",
                        )
                    )
            else:
                issues.append(
                    (
                        "ERROR",
                        f"{file_name} line {row_idx}: Value '{value}' for '{col_name}' is not a valid date (YYYY-MM-DD [HH:MM[:SS]])",
                    )
                )
        return issues

    def _check_numeric_range(
        self, value: str, col_name: str, col_def: dict, file_name: str, row_idx: int
    ) -> list:
        """Checks if a numeric value is within Min/Max or WarnMin/Max ranges."""
        range_keys = ["MinValue", "MaxValue", "WarnMinValue", "WarnMaxValue"]
        if not any(col_def.get(k) not in [None, ""] for k in range_keys):
            return []

        issues = []
        try:
            num_val = float(value)
            # Mandatory bounds (ERROR)
            for key, op, msg in [
                ("MinValue", lambda a, b: a < b, "less than MinValue"),
                ("MaxValue", lambda a, b: a > b, "greater than MaxValue"),
            ]:
                limit = col_def.get(key)
                if limit not in [None, ""] and op(num_val, float(limit)):
                    issues.append(
                        (
                            "ERROR",
                            f"{file_name} line {row_idx}: Value {num_val} for '{col_name}' is {msg} {limit}",
                        )
                    )

            # Warning bounds (WARNING)
            for key, op, msg in [
                ("WarnMinValue", lambda a, b: a < b, "less than WarnMinValue"),
                ("WarnMaxValue", lambda a, b: a > b, "greater than WarnMaxValue"),
            ]:
                limit = col_def.get(key)
                if limit not in [None, ""] and op(num_val, float(limit)):
                    issues.append(
                        (
                            "WARNING",
                            f"{file_name} line {row_idx}: Value {num_val} for '{col_name}' is {msg} {limit}",
                        )
                    )
        except ValueError:
            issues.append(
                (
                    "ERROR",
                    f"{file_name} line {row_idx}: Value '{value}' for '{col_name}' is not numeric but has numeric constraints",
                )
            )
        return issues

    def validate_data_content(self, file_path, modality, root_dir):
        """Validate data content against constraints in sidecar"""
        issues = []

        # Only validate content for tabular data modalities
        if modality not in ["survey", "biometrics"]:
            return issues

        sidecar_path = resolve_sidecar_path(file_path, root_dir, self.library_path)
        if not os.path.exists(sidecar_path):
            # Missing sidecar is already reported by validate_sidecar
            return issues

        try:
            # Check for empty file
            if os.path.getsize(file_path) == 0:
                return [
                    (
                        "ERROR",
                        f"File {os.path.basename(file_path)} is empty. If data is missing, please delete the file.",
                    )
                ]

            # Load sidecar
            sidecar_content = CrossPlatformFile.read_text(sidecar_path)
            sidecar_data = json.loads(sidecar_content)

            # Build flat lookup table for validation, resolving AliasOf and Aliases
            effective_defs = self._build_effective_defs(sidecar_data)

            # Read TSV file
            file_name = os.path.basename(file_path)
            with open(file_path, "r", newline="", encoding="utf-8") as tsvfile:
                reader = csv.DictReader(tsvfile, delimiter="\t")

                if not reader.fieldnames:
                    return [
                        (
                            "ERROR",
                            f"File {file_name} is not a valid TSV (no header found).",
                        )
                    ]

                row_count = 0
                for row_idx, row in enumerate(
                    reader, start=2
                ):  # start=2 for 1-based line number (header is 1)
                    row_count += 1

                    # Check for completely empty row (all values are empty strings)
                    if all(v is None or v.strip() == "" for v in row.values()):
                        issues.append(
                            (
                                "WARNING",
                                f"{file_name} line {row_idx}: Row contains only empty values. Use 'n/a' for missing data, or delete the file if no data exists.",
                            )
                        )
                        continue

                    for col_name, value in row.items():
                        if col_name in effective_defs:
                            col_def = effective_defs[col_name]

                            # Skip empty values
                            if (
                                value is None
                                or value.strip() == ""
                                or value.lower() in ("n/a", "na")
                            ):
                                continue

                            # Apply validation helpers
                            issues.extend(
                                self._check_allowed_values(
                                    value, col_name, col_def, file_name, row_idx
                                )
                            )
                            issues.extend(
                                self._check_data_type(
                                    value, col_name, col_def, file_name, row_idx
                                )
                            )
                            issues.extend(
                                self._check_numeric_range(
                                    value, col_name, col_def, file_name, row_idx
                                )
                            )

                if row_count == 0:
                    issues.append(
                        (
                            "WARNING",
                            f"File {file_name} contains no data rows. If data is missing, please delete the file.",
                        )
                    )

        except Exception as e:
            issues.append(
                (
                    "ERROR",
                    f"Error validating content of {os.path.basename(file_path)}: {str(e)}",
                )
            )

        return issues

    def validate_filename(self, filename, modality, subject_id=None, session_id=None):
        """Validate filename against BIDS conventions and modality patterns"""
        issues = []

        # For standard BIDS modalities, skip detailed validation
        # The BIDS validator handles these properly
        if modality in BIDS_MODALITIES:
            # Only do basic subject/session consistency checks
            if subject_id and not filename.startswith(subject_id + "_"):
                issues.append(
                    ("WARNING", f"Filename {filename} does not start with subject ID {subject_id}")
                )
            if session_id:
                expected_prefix = f"{subject_id}_{session_id}_"
                if not filename.startswith(expected_prefix):
                    issues.append(
                        ("WARNING", f"Filename {filename} does not match session directory {session_id}")
                    )
            return issues  # Skip PRISM-specific validation for BIDS modalities

        # Cross-platform filename validation (PRISM modalities only)
        platform_issues = validate_filename_cross_platform(filename)
        for issue in platform_issues:
            issues.append(("WARNING", issue))

        base, ext = split_compound_ext(filename)
        pattern = re.compile(MODALITY_PATTERNS.get(modality, r".*"))
        is_sidecar = filename.endswith(".json")

        # Check BIDS naming for PRISM files
        if not BIDS_REGEX.match(base):
            issues.append(("ERROR", f"Invalid BIDS filename format: {filename}"))

        # Check modality pattern (strict for survey/biometrics)
        if modality in {"survey", "biometrics"}:
            if not pattern.match(filename):
                issues.append(
                    (
                        "ERROR",
                        f"Filename doesn't match expected pattern for {modality}: {filename}",
                    )
                )
        elif modality in PRISM_MODALITIES:
            if not is_sidecar and not pattern.match(filename):
                issues.append(
                    (
                        "WARNING",
                        f"Filename doesn't match expected pattern for {modality}: {filename}",
                    )
                )

        # Check subject consistency
        if subject_id:
            if not filename.startswith(subject_id + "_"):
                issues.append(
                    (
                        "ERROR",
                        f"Filename {filename} does not start with subject ID {subject_id}",
                    )
                )

        # Check session consistency
        if session_id:
            # Expecting sub-XX_ses-YY_...
            expected_prefix = f"{subject_id}_{session_id}_"
            if not filename.startswith(expected_prefix):
                issues.append(
                    (
                        "ERROR",
                        f"Filename {filename} does not match session directory {session_id}",
                    )
                )
        elif subject_id:
            # If no session directory, filename should not contain session entity
            # But we need to be careful not to match "ses-" if it appears elsewhere (unlikely in BIDS but possible)
            # BIDS session entity is always "_ses-<label>"
            if "_ses-" in filename:
                issues.append(
                    (
                        "ERROR",
                        f"Filename {filename} contains session entity but is not in a session directory",
                    )
                )

        return issues

    def validate_sidecar(self, file_path, modality, root_dir):
        """Validate JSON sidecar against schema"""
        
        # Skip sidecar validation for standard BIDS modalities
        # The BIDS validator handles these
        if modality in BIDS_MODALITIES:
            return []
        
        sidecar_path = resolve_sidecar_path(file_path, root_dir, self.library_path)
        issues = []

        if not os.path.exists(sidecar_path):
            return [("ERROR", f"Missing sidecar for {normalize_path(file_path)}")]

        try:
            # Use cross-platform file reading
            content = CrossPlatformFile.read_text(sidecar_path)
            sidecar_data = json.loads(content)

            # Validate against schema if available (PRISM modalities only)
            schema = self.schemas.get(modality)
            if schema:
                # Version compatibility checks (only warns when explicitly specified and incompatible)
                issues.extend(validate_schema_version(sidecar_data, schema))
                validate(instance=sidecar_data, schema=schema)

        except ValidationError as e:
            issues.append(
                ("ERROR", f"{normalize_path(sidecar_path)} schema error: {e.message}")
            )
        except json.JSONDecodeError as e:
            issues.append(
                ("ERROR", f"{normalize_path(sidecar_path)} is not valid JSON: {e}")
            )
        except Exception as e:
            issues.append(
                ("ERROR", f"Error processing {normalize_path(sidecar_path)}: {e}")
            )

        return issues
