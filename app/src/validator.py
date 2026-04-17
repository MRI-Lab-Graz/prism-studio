"""
Core validation logic for prism
"""

import os
import re
import json
import csv
import gzip
from pathlib import Path
from datetime import datetime
from jsonschema import validate, ValidationError
from schema_manager import validate_schema_version, apply_schema_validation_profile
from cross_platform import (
    normalize_path,
    safe_path_join,
    CrossPlatformFile,
    validate_filename_cross_platform,
)

# PRISM-specific modalities that we validate with our schemas
# Standard BIDS modalities (anat, func, fmap, dwi, eeg) are passed through
# and should be validated by the optional BIDS validator instead
PRISM_MODALITIES = {
    "survey",
    "biometrics",
    "environment",
    "events",
    "physio",
    "physiological",
    "eyetracking",
}

# Standard BIDS modalities - we only do minimal checks (subject/session consistency)
# Full validation is delegated to the BIDS validator
BIDS_MODALITIES = {"anat", "func", "fmap", "dwi", "eeg"}

# Modality patterns (only enforced for PRISM modalities)
MODALITY_PATTERNS = {
    # PRISM survey/biometrics must carry explicit suffixes
    "survey": r".+_survey\.(tsv|json)$",
    "biometrics": r".+_biometrics\.(tsv|json)$",
    "environment": r".+_recording-[a-zA-Z0-9]+_environment\.(tsv|tsv\.gz|json)$",
    "events": r".+_events\.tsv$",
    "physio": r".+(_recording-(ecg|cardiac|puls|resp|eda|ppg|emg|temp|bp|spo2|trigger|[a-zA-Z0-9]+))?_physio\.(tsv|tsv\.gz|json|edf)$",
    "physiological": r".+(_recording-(ecg|cardiac|puls|resp|eda|ppg|emg|temp|bp|spo2|trigger|[a-zA-Z0-9]+))?_physio\.(tsv|tsv\.gz|json|edf)$",
    "eyetracking": r".+(_trackedEye-(left|right|both))?_(eyetrack|eye|gaze)\.(tsv|tsv\.gz|json|edf|asc)$",
}

# BIDS naming patterns
BIDS_REGEX = re.compile(
    r"^sub-[a-zA-Z0-9]+"  # subject
    r"(_ses-[a-zA-Z0-9]{2,})?"  # optional session (min 2 chars, e.g., ses-01 not ses-1)
    r"(_[a-zA-Z0-9]+-[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*)*"  # key-value pairs; values may contain hyphens (e.g., task-bfi-s)
    r"(_[a-zA-Z0-9]+)?$"  # generic suffix (e.g., _dwi, _T1w, _bold, _physio, _events)
)

MRI_SUFFIX_REGEX = re.compile(
    r"_(T1w|T2w|T2star|FLAIR|PD|PDw|T1map|T2map|bold|dwi|magnitude1|magnitude2|phasediff|fieldmap|epi|sbref)$"
)

# File extensions that need special handling
COMPOUND_EXTS = (".nii.gz", ".tsv.gz", ".edf.gz")

ENV_REQUIRED_COLUMNS = {
    "subject_id",
    "session_id",
    "filename",
    "relative_time",
    "hour_bin",
    "season_code",
    "sun_phase",
    "sun_hours_today",
    "hours_since_sun",
    "temp_c",
    "humidity_pct",
    "pressure_hpa",
    "precip_mm",
    "wind_speed_ms",
    "cloud_cover_pct",
    "weather_regime",
    "aqi",
    "pm25_ug_m3",
    "pm10_ug_m3",
    "no2_ug_m3",
    "o3_ug_m3",
    "pollen_total",
    "pollen_birch",
    "pollen_grass",
    "pollen_risk_bin",
}

ENV_FORBIDDEN_COLUMNS = {
    "date",
    "datetime",
    "timestamp",
    "acquisition_datetime",
    "acquisition_time",
    "acquisition_date",
    "latitude",
    "longitude",
    "lat",
    "lon",
    "location",
    "location_label",
    "source_weather",
    "source_air_quality",
    "source_pollen",
}

ENV_NUMERIC_COLUMNS = {
    "sun_hours_today",
    "hours_since_sun",
    "elevation_m",
    "temp_c",
    "humidity_pct",
    "pressure_hpa",
    "precip_mm",
    "wind_speed_ms",
    "cloud_cover_pct",
    "aqi",
    "pm25_ug_m3",
    "pm10_ug_m3",
    "no2_ug_m3",
    "o3_ug_m3",
    "pollen_total",
    "pollen_birch",
    "pollen_grass",
}


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
    # Capture the value up to the next underscore (BIDS entity separator) or end
    # of string.  Values may contain hyphens (e.g., task-bfi-s).
    match = re.search(rf"_{key}-([^_]+)", stem)
    if match:
        return match.group(1)
    return None


def _resolve_survey_variant(file_path: str, sidecar_data: dict | None) -> str | None:
    """Resolve variant from filename acq entity or sidecar Study.Version."""
    stem = Path(file_path).stem.replace(".tsv", "").replace(".json", "")
    acq_value = _extract_entity_value(stem, "acq")
    if acq_value:
        return acq_value

    if isinstance(sidecar_data, dict):
        study = sidecar_data.get("Study", {})
        if isinstance(study, dict):
            version = study.get("Version")
            if version:
                return str(version)
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
    acq_value = _extract_entity_value(stem, "acq")

    def _value_candidates(base_value):
        if not base_value:
            return []
        candidates = []
        if acq_value:
            candidates.append(f"{base_value}_acq-{acq_value}")
        candidates.append(base_value)
        return candidates

    label_candidates = []
    for survey_candidate in _value_candidates(survey_value):
        label_candidates.append(("survey", survey_candidate))
    for biometrics_candidate in _value_candidates(biometrics_value):
        label_candidates.append(("biometrics", biometrics_candidate))
    if task_value:
        for task_candidate in _value_candidates(task_value):
            label_candidates.append(("task", task_candidate))
        if not survey_value and not biometrics_value:
            for task_candidate in _value_candidates(task_value):
                label_candidates.append(("survey", task_candidate))
                label_candidates.append(("biometrics", task_candidate))

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


def _deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries. Override values take precedence.

    For nested dicts, recursively merge. For other types, override replaces base.
    This implements BIDS inheritance where subject-level values override root-level.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _find_inherited_root_sidecar(file_path: str, root_dir: str) -> str | None:
    """Find a dataset-level sidecar that can provide inherited defaults.

    Supports task-based and legacy survey/biometrics naming conventions so
    root-level metadata can be merged with subject-level overrides.
    """
    file_path = normalize_path(file_path)
    fname = os.path.basename(file_path)
    stem, _ext = split_compound_ext(fname)

    suffix = ""
    if "_" in stem:
        suffix = stem.split("_")[-1]
    if not suffix:
        return None

    survey_value = _extract_entity_value(stem, "survey")
    biometrics_value = _extract_entity_value(stem, "biometrics")
    task_value = _extract_entity_value(stem, "task")
    acq_value = _extract_entity_value(stem, "acq")

    def _value_candidates(base_value):
        if not base_value:
            return []
        candidates = []
        if acq_value:
            candidates.append(f"{base_value}_acq-{acq_value}")
        candidates.append(base_value)
        return candidates

    candidate_names = []
    for survey_candidate in _value_candidates(survey_value):
        candidate_names.append(f"survey-{survey_candidate}_{suffix}.json")
    for biometrics_candidate in _value_candidates(biometrics_value):
        candidate_names.append(f"biometrics-{biometrics_candidate}_{suffix}.json")
    if task_value:
        for task_candidate in _value_candidates(task_value):
            candidate_names.append(f"task-{task_candidate}_{suffix}.json")
        # Backward-compatible fallback: some datasets use survey-/biometrics-
        # naming with task labels.
        for task_candidate in _value_candidates(task_value):
            candidate_names.append(f"survey-{task_candidate}_{suffix}.json")
            candidate_names.append(f"biometrics-{task_candidate}_{suffix}.json")

    # Also support inherited sidecars that keep additional entities (for example
    # task-rest_recording-ecg_physio.json) while omitting subject/session.
    parts = stem.split("_") if stem else []
    non_subject_session_parts = [
        part
        for part in parts
        if not part.startswith("sub-")
        and not part.startswith("ses-")
        and not part.startswith("run-")
    ]
    if non_subject_session_parts:
        candidate_names.append(f"{'_'.join(non_subject_session_parts)}.json")

    # De-duplicate while preserving order for deterministic lookup.
    seen_names = set()
    deduped_candidate_names = []
    for name in candidate_names:
        if name in seen_names:
            continue
        seen_names.add(name)
        deduped_candidate_names.append(name)
    candidate_names = deduped_candidate_names

    # BIDS inheritance: search from file directory up to dataset root, so
    # nearest matching ancestor metadata takes precedence.
    root_abs = os.path.abspath(root_dir)
    search_dirs = []
    current_dir = os.path.dirname(os.path.abspath(file_path))
    while True:
        search_dirs.append(current_dir)
        if current_dir == root_abs:
            break
        parent = os.path.dirname(current_dir)
        if parent == current_dir or not parent.startswith(root_abs):
            break
        current_dir = parent

    # Keep historical fixed locations for backward compatibility.
    search_dirs.extend(
        [
            root_abs,
            safe_path_join(root_abs, "surveys"),
            safe_path_join(root_abs, "biometrics"),
            safe_path_join(root_abs, "physio"),
            safe_path_join(root_abs, "physiological"),
        ]
    )

    seen_dirs = set()
    deduped_search_dirs = []
    for directory in search_dirs:
        if not directory or directory in seen_dirs:
            continue
        seen_dirs.add(directory)
        deduped_search_dirs.append(directory)
    search_dirs = deduped_search_dirs

    for directory in search_dirs:
        if not directory:
            continue
        for candidate_name in candidate_names:
            candidate_path = safe_path_join(directory, candidate_name)
            if os.path.exists(candidate_path):
                return candidate_path

    return None


def resolve_inherited_sidecar(
    file_path: str, root_dir: str, library_path: str | None = None
) -> tuple[dict | None, str | None]:
    """
    Build inherited sidecar content following BIDS inheritance principle.

    Resolution order:
    1. Root-level sidecar (task-{name}_{suffix}.json at dataset root) - provides defaults
    2. Subject-level sidecar (alongside the data file) - overrides root-level
    3. Library sidecar (from global library) - fallback if no local sidecars

    The subject-level sidecar is OPTIONAL. If only root-level exists, it's used.
    If both exist, they are deep-merged with subject-level values taking precedence.

    Args:
        file_path: Path to the data file
        root_dir: Dataset root directory
        library_path: Optional path to template library

    Returns:
        Tuple of (merged_sidecar_data, primary_sidecar_path)
        - merged_sidecar_data: The merged sidecar content (or None if not found)
        - primary_sidecar_path: Path to report errors against (subject-level if exists, else root)
    """
    # Find subject-level sidecar (directly alongside data file)
    subject_sidecar_path = derive_sidecar_path(file_path)
    subject_sidecar_exists = os.path.exists(subject_sidecar_path)

    # Find root-level sidecar
    root_sidecar_path = _find_inherited_root_sidecar(file_path, root_dir)
    root_sidecar_exists = root_sidecar_path and os.path.exists(root_sidecar_path)

    # Load sidecars
    root_data = None
    subject_data = None

    if root_sidecar_exists:
        try:
            content = CrossPlatformFile.read_text(root_sidecar_path)
            root_data = json.loads(content)
        except (json.JSONDecodeError, Exception):
            root_data = None

    if subject_sidecar_exists:
        try:
            content = CrossPlatformFile.read_text(subject_sidecar_path)
            subject_data = json.loads(content)
        except (json.JSONDecodeError, Exception):
            subject_data = None

    # Merge according to BIDS inheritance
    if root_data and subject_data:
        # Both exist: merge (subject overrides root)
        merged = _deep_merge(root_data, subject_data)
        return merged, subject_sidecar_path
    elif subject_data:
        # Only subject-level exists
        return subject_data, subject_sidecar_path
    elif root_data:
        # Only root-level exists (subject-level is optional)
        return root_data, root_sidecar_path

    # Neither exists locally - try library fallback via existing resolution
    library_sidecar = resolve_sidecar_path(file_path, root_dir, library_path)
    if library_sidecar and os.path.exists(library_sidecar):
        try:
            content = CrossPlatformFile.read_text(library_sidecar)
            library_data = json.loads(content)
            return library_data, library_sidecar
        except (json.JSONDecodeError, Exception):
            pass

    return None, None


class DatasetValidator:
    """Main dataset validation class"""

    def __init__(self, schemas=None, library_path=None):
        self.schemas = schemas or {}
        self.library_path = library_path
        self._sidecar_path_cache = {}
        self._inherited_sidecar_cache = {}
        self._sidecar_json_cache = {}
        self._original_name_cache = {}

    def _sidecar_cache_key(self, file_path: str, root_dir: str) -> tuple:
        """Build a stable cache key for sidecar resolution within one run."""
        normalized_library = (
            normalize_path(self.library_path) if self.library_path else None
        )
        return (
            normalize_path(file_path),
            os.path.abspath(root_dir),
            normalized_library,
        )

    def _resolve_sidecar_path_cached(self, file_path: str, root_dir: str) -> str:
        """Resolve sidecar path once per file/root combination."""
        cache_key = self._sidecar_cache_key(file_path, root_dir)
        cached_path = self._sidecar_path_cache.get(cache_key)
        if cached_path is not None:
            return cached_path

        resolved_path = resolve_sidecar_path(file_path, root_dir, self.library_path)
        self._sidecar_path_cache[cache_key] = resolved_path
        return resolved_path

    def _load_sidecar_json_cached(self, sidecar_path: str | None):
        """Read and parse a sidecar JSON file at most once per validation run."""
        if not sidecar_path or not os.path.exists(sidecar_path):
            return None

        normalized_path = normalize_path(sidecar_path)
        if normalized_path in self._sidecar_json_cache:
            return self._sidecar_json_cache[normalized_path]

        parsed = None
        try:
            content = CrossPlatformFile.read_text(sidecar_path)
            parsed = json.loads(content)
        except (json.JSONDecodeError, Exception):
            parsed = None

        self._sidecar_json_cache[normalized_path] = parsed
        return parsed

    def _resolve_inherited_sidecar_cached(
        self, file_path: str, root_dir: str
    ) -> tuple[dict | None, str | None]:
        """Resolve inherited sidecars once per file/root combination."""
        cache_key = self._sidecar_cache_key(file_path, root_dir)
        cached_result = self._inherited_sidecar_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        subject_sidecar_path = derive_sidecar_path(file_path)
        root_sidecar_path = _find_inherited_root_sidecar(file_path, root_dir)

        root_data = self._load_sidecar_json_cached(root_sidecar_path)
        subject_data = self._load_sidecar_json_cached(subject_sidecar_path)

        result: tuple[dict | None, str | None]

        if root_data and subject_data:
            result = (_deep_merge(root_data, subject_data), subject_sidecar_path)
        elif subject_data:
            result = (subject_data, subject_sidecar_path)
        elif root_data:
            result = (root_data, root_sidecar_path)
        else:
            library_sidecar = self._resolve_sidecar_path_cached(file_path, root_dir)
            library_data = self._load_sidecar_json_cached(library_sidecar)
            if library_data:
                result = (library_data, library_sidecar)
            else:
                result = (None, None)

        self._inherited_sidecar_cache[cache_key] = result
        return result

    def get_sidecar_original_name(self, file_path: str, root_dir: str):
        """Return Study.OriginalName from the effective sidecar, if present."""
        cache_key = self._sidecar_cache_key(file_path, root_dir)
        if cache_key in self._original_name_cache:
            return self._original_name_cache[cache_key]

        sidecar_data, _sidecar_path = self._resolve_inherited_sidecar_cached(
            file_path, root_dir
        )
        original_name = None
        if isinstance(sidecar_data, dict):
            study = sidecar_data.get("Study")
            if isinstance(study, dict):
                original_name = study.get("OriginalName")

        self._original_name_cache[cache_key] = original_name
        return original_name

    def _is_official_template_path(self, sidecar_path: str | None) -> bool:
        """Return True when sidecar path points to an official template library."""
        if not sidecar_path:
            return False
        normalized = normalize_path(sidecar_path).lower()
        return "/official/" in normalized or normalized.endswith("/official")

    def _schema_for_sidecar(self, modality: str, sidecar_path: str | None):
        """Return effective schema for a sidecar by validation profile."""
        schema = self.schemas.get(modality)
        if not schema:
            return None

        profile = (
            "official" if self._is_official_template_path(sidecar_path) else "project"
        )
        return apply_schema_validation_profile(schema, profile=profile)

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
        if not dtype and col_def.get("Unit") == "date":
            dtype = "date"

        if not dtype:
            return []

        if dtype == "integer":
            try:
                # Support both periods and commas as decimal separators (EU locales use commas)
                if not float(value.replace(",", ".")).is_integer():
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
                # Support both periods and commas as decimal separators (EU locales use commas)
                float(value.replace(",", "."))
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
                if date_val is not None and date_val > datetime.now():
                    issues.append(
                        (
                            "WARNING",
                            f"{file_name} line {row_idx}: Date '{value}' for '{col_name}' is in the future",
                        )
                    )
                if date_val is not None and date_val.year < 1900:
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
            # Support both periods and commas as decimal separators (EU locales use commas)
            num_val = float(value.replace(",", "."))
            # Mandatory bounds (ERROR)
            for key, op, msg in [
                ("MinValue", lambda a, b: a < b, "less than MinValue"),
                ("MaxValue", lambda a, b: a > b, "greater than MaxValue"),
            ]:
                limit = col_def.get(key)
                if limit is not None and limit != "":
                    limit_num = float(limit)
                    if op(num_val, limit_num):
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
                if limit is not None and limit != "":
                    limit_num = float(limit)
                    if op(num_val, limit_num):
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

    def _extract_bids_entities(
        self, file_path: str
    ) -> tuple[str, str | None, str | None]:
        """Extract (task_name, session, run) from a BIDS-style file path.

        Returns empty string for task_name if the entity is not found.
        """
        stem = Path(file_path).stem.replace(".tsv", "").replace(".json", "")
        parts = stem.split("_")
        task_name = ""
        session = None
        run = None
        for part in parts:
            if part.startswith("task-"):
                task_name = part[len("task-") :]
            elif part.startswith("ses-"):
                session = part
            elif part.startswith("run-"):
                run = part
        # Also check directory parts for session
        if session is None:
            for p in Path(file_path).parts:
                if p.startswith("ses-"):
                    session = p
                    break
        return task_name, session, run

    def _apply_variant_col_def(
        self, col_def: dict, resolved_version: str | None
    ) -> dict:
        """Return a col_def with VariantScales overrides applied for resolved_version.

        If resolved_version is None or the item has no VariantScales, returns col_def unchanged.
        """
        if not resolved_version:
            return col_def
        variant_scales = col_def.get("VariantScales")
        if not isinstance(variant_scales, list):
            return col_def
        for entry in variant_scales:
            if isinstance(entry, dict) and entry.get("VariantID") == resolved_version:
                # Merge: variant entry overrides top-level for scale/range keys
                merged = dict(col_def)
                for key in (
                    "ScaleType",
                    "DataType",
                    "MinValue",
                    "MaxValue",
                    "WarnMinValue",
                    "WarnMaxValue",
                    "AllowedValues",
                    "Levels",
                    "Unit",
                ):
                    if key in entry and entry[key] is not None:
                        merged[key] = entry[key]
                return merged
        return col_def

    def validate_data_content(self, file_path, modality, root_dir):
        """Validate data content against constraints in sidecar (with BIDS inheritance)"""
        issues = []

        if modality == "environment":
            return self._validate_environment_content(file_path)

        # Only validate content for tabular data modalities
        if modality not in ["survey", "biometrics"]:
            return issues

        # Use BIDS inheritance to resolve sidecar (root-level + subject-level merged)
        sidecar_data, sidecar_path = self._resolve_inherited_sidecar_cached(
            file_path, root_dir
        )

        if sidecar_data is None:
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

            # sidecar_data is already loaded and merged by resolve_inherited_sidecar

            # Build flat lookup table for validation, resolving AliasOf and Aliases
            effective_defs = self._build_effective_defs(sidecar_data)

            # Resolve survey variant for this file (multi-version support)
            resolved_version: str | None = None
            excluded_columns: set[str] = set()
            if modality == "survey":
                resolved_version = _resolve_survey_variant(file_path, sidecar_data)
                if resolved_version:
                    # Identify items not applicable to this variant
                    for col, cdef in effective_defs.items():
                        applicable = cdef.get("ApplicableVersions")
                        if (
                            isinstance(applicable, list)
                            and applicable
                            and resolved_version not in applicable
                        ):
                            excluded_columns.add(col)

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

                            # Warn if column should not appear in this variant
                            if col_name in excluded_columns:
                                issues.append(
                                    (
                                        "WARNING",
                                        f"{file_name} line {row_idx}: Column '{col_name}' is not in "
                                        f"ApplicableVersions for variant '{resolved_version}'. "
                                        "Check that the correct survey variant was administered.",
                                    )
                                )
                                continue

                            # Apply variant-specific scale overrides (VariantScales)
                            col_def = self._apply_variant_col_def(
                                col_def, resolved_version
                            )

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

    def _validate_environment_content(self, file_path):
        issues = []
        file_name = os.path.basename(file_path)

        try:
            if os.path.getsize(file_path) == 0:
                return [
                    (
                        "ERROR",
                        f"File {file_name} is empty. If data is missing, please delete the file.",
                    )
                ]

            opener = gzip.open if file_path.endswith(".tsv.gz") else open
            with opener(file_path, "rt", newline="", encoding="utf-8") as tsvfile:
                reader = csv.DictReader(tsvfile, delimiter="\t")
                if not reader.fieldnames:
                    return [
                        (
                            "ERROR",
                            f"File {file_name} is not a valid TSV (no header found).",
                        )
                    ]

                headers = [h.strip() for h in reader.fieldnames if h]
                header_set = set(headers)
                header_lower = {h.lower() for h in header_set}

                missing = sorted(ENV_REQUIRED_COLUMNS - header_set)
                if missing:
                    issues.append(
                        (
                            "ERROR",
                            f"{file_name}: Missing required environment columns: {', '.join(missing)}",
                        )
                    )

                forbidden = sorted(header_lower.intersection(ENV_FORBIDDEN_COLUMNS))
                if forbidden:
                    issues.append(
                        (
                            "ERROR",
                            f"{file_name}: Forbidden privacy-sensitive columns found: {', '.join(forbidden)}",
                        )
                    )

                row_count = 0
                for row_idx, row in enumerate(reader, start=2):
                    row_count += 1

                    if all(v is None or str(v).strip() == "" for v in row.values()):
                        issues.append(
                            (
                                "WARNING",
                                f"{file_name} line {row_idx}: Row contains only empty values.",
                            )
                        )
                        continue

                    hour_bin = (row.get("hour_bin") or "").strip()
                    if hour_bin and hour_bin not in {
                        "night",
                        "morning",
                        "afternoon",
                        "evening",
                        "unknown",
                    }:
                        issues.append(
                            (
                                "ERROR",
                                f"{file_name} line {row_idx}: Invalid hour_bin '{hour_bin}'",
                            )
                        )

                    season = (row.get("season_code") or "").strip()
                    if season and season not in {
                        "spring",
                        "summer",
                        "autumn",
                        "winter",
                        "unknown",
                    }:
                        issues.append(
                            (
                                "ERROR",
                                f"{file_name} line {row_idx}: Invalid season_code '{season}'",
                            )
                        )

                    pollen_risk = (row.get("pollen_risk_bin") or "").strip()
                    if pollen_risk and pollen_risk not in {
                        "low",
                        "medium",
                        "high",
                        "very_high",
                    }:
                        issues.append(
                            (
                                "ERROR",
                                f"{file_name} line {row_idx}: Invalid pollen_risk_bin '{pollen_risk}'",
                            )
                        )

                    weather_regime = (row.get("weather_regime") or "").strip()
                    if weather_regime and weather_regime not in {
                        "hochdruck",
                        "tiefdruck",
                        "frontal",
                    }:
                        issues.append(
                            (
                                "ERROR",
                                f"{file_name} line {row_idx}: Invalid weather_regime '{weather_regime}'",
                            )
                        )

                    heatwave_status = (row.get("heatwave_status") or "").strip()
                    if heatwave_status and heatwave_status not in {
                        "normal",
                        "warm_day",
                        "hot_day",
                        "heatwave",
                        "unknown",
                    }:
                        issues.append(
                            (
                                "ERROR",
                                f"{file_name} line {row_idx}: Invalid heatwave_status '{heatwave_status}'",
                            )
                        )

                    for column_name in ENV_NUMERIC_COLUMNS:
                        value = (row.get(column_name) or "").strip()
                        if not value:
                            continue
                        try:
                            float(value)
                        except ValueError:
                            issues.append(
                                (
                                    "ERROR",
                                    f"{file_name} line {row_idx}: Column '{column_name}' must be numeric (got '{value}')",
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
                    f"Error validating content of {file_name}: {str(e)}",
                )
            )

        return issues

    def validate_filename(
        self,
        filename,
        modality,
        subject_id=None,
        session_id=None,
        file_path=None,
    ):
        """Validate filename against BIDS conventions and modality patterns"""
        issues = []

        if modality == "environment" and file_path:
            path_parts = Path(normalize_path(file_path)).parts
            has_subject = any(part.startswith("sub-") for part in path_parts)
            has_session = any(part.startswith("ses-") for part in path_parts)
            has_environment_dir = "environment" in path_parts
            if not (has_subject and has_session and has_environment_dir):
                issues.append(
                    (
                        "ERROR",
                        (
                            "Environment files must be stored under "
                            "sub-*/ses-*/environment/"
                        ),
                    )
                )

        # For standard BIDS modalities, skip detailed validation
        # The BIDS validator handles these properly
        if modality in BIDS_MODALITIES:
            # Only do basic subject/session consistency checks
            if subject_id and not filename.startswith(subject_id + "_"):
                issues.append(
                    (
                        "WARNING",
                        f"Filename {filename} does not start with subject ID {subject_id}",
                    )
                )
            if session_id:
                expected_prefix = f"{subject_id}_{session_id}_"
                if not filename.startswith(expected_prefix):
                    issues.append(
                        (
                            "WARNING",
                            f"Filename {filename} does not match session directory {session_id}",
                        )
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
                        f"Filename doesn't match expected pattern for modality '{modality}': {filename}",
                    )
                )
        elif modality == "environment":
            if not is_sidecar and not pattern.match(filename):
                issues.append(
                    (
                        "ERROR",
                        f"Filename doesn't match expected pattern for modality '{modality}': {filename}",
                    )
                )
        elif modality in PRISM_MODALITIES:
            if not is_sidecar and not pattern.match(filename):
                issues.append(
                    (
                        "WARNING",
                        f"Filename doesn't match expected pattern for modality '{modality}': {filename}",
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
        """Validate JSON sidecar against schema (with BIDS inheritance)"""

        # Skip sidecar validation for standard BIDS modalities
        # The BIDS validator handles these
        if modality in BIDS_MODALITIES:
            return []

        issues = []

        # Use BIDS inheritance to resolve sidecar (root-level + subject-level merged)
        sidecar_data, sidecar_path = self._resolve_inherited_sidecar_cached(
            file_path, root_dir
        )

        if sidecar_data is None:
            return [("ERROR", f"Missing sidecar for {normalize_path(file_path)}")]

        try:
            # Validate against schema if available (PRISM modalities only)
            schema = self._schema_for_sidecar(modality, sidecar_path)
            if schema:
                # Version compatibility checks (only warns when explicitly specified and incompatible)
                issues.extend(validate_schema_version(sidecar_data, schema))
                validate(instance=sidecar_data, schema=schema)

        except ValidationError as e:
            # Format message to be more descriptive (include field path)
            field_path = " -> ".join([str(p) for p in e.path])
            prefix = f"{field_path}: " if field_path else ""
            issues.append(
                (
                    "ERROR",
                    f"{normalize_path(sidecar_path)} schema error: {prefix}{e.message}",
                )
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
