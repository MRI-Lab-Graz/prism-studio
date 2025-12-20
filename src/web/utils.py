"""
Web interface utilities for prism.
Common helper functions used across web routes.
"""

import os
import re
from typing import Optional, Any, Dict


# System files to filter out
SYSTEM_FILES = {
    ".DS_Store",
    "._.DS_Store",
    "Thumbs.db",
    "ehthumbs.db",
    "Desktop.ini",
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    ".TemporaryItems",
}


def is_system_file(filename: str) -> bool:
    """Check if a file is a system file that should be ignored."""
    if not filename:
        return True
    if filename in SYSTEM_FILES:
        return True
    if filename.startswith("._") or filename.startswith(".#"):
        return True
    return False


def strip_temp_path(
    file_path: str, dataset_path: Optional[str] = None
) -> Optional[str]:
    """Strip temporary folder path prefix and keep only relative path from dataset root."""
    if not file_path:
        return None

    # Normalize separators
    file_path = file_path.replace("\\", "/")

    # If it's a temp path, try to extract the relative path
    temp_patterns = [
        "/tmp/",
        "/T/prism_validator_",
        "/var/folders/",
        "prism_validator_",
        "renamed_files",
    ]
    is_temp_path = any(p in file_path for p in temp_patterns)

    if is_temp_path:
        # Find the dataset root marker - typically after 'dataset/'
        if "/dataset/" in file_path:
            parts = file_path.split("/dataset/", 1)
            if len(parts) > 1:
                return parts[1]

        # Look for common BIDS/PRISM root markers
        # We look for the last occurrence of these markers to get the most specific relative path
        markers = ["sub-", "ses-", "dataset_description.json", "participants.tsv"]
        best_match = None
        for marker in markers:
            if marker in file_path:
                idx = file_path.rfind(marker)
                match_path = file_path[idx:]
                if not best_match or len(match_path) < len(best_match):
                    best_match = match_path
        
        if best_match:
            return best_match

    # If dataset_path is a temp directory, strip it
    if dataset_path:
        dataset_path = dataset_path.replace("\\", "/")
        if file_path.startswith(dataset_path):
            relative = file_path[len(dataset_path) :].lstrip("/")
            return relative if relative else file_path

    return file_path


def strip_temp_path_from_message(msg: str) -> str:
    """Remove temp folder paths from message text."""
    if not msg:
        return msg
    
    # Replace temp folder paths in the message with just the relative path
    # We look for the last occurrence of a temp-like folder name in a path
    # and strip everything before it (including the temp folder itself)
    temp_folders = [
        'tmp', 
        'var/folders', 
        'T', 
        r'prism_validator_[^\s,:/]+', 
        r'renamed_files[^\s,:/]*'
    ]
    
    for folder in temp_folders:
        # Match something like /.../tmp/ or /.../renamed_files-2/
        # and replace with nothing
        msg = re.sub(r"(/[^\s,:]+)?/" + folder + r"/", "", msg)
    
    # Clean up any remaining "dataset/" prefix if it was part of a temp path
    msg = msg.replace("dataset/", "")
    
    return msg.strip()


def extract_path_from_message(
    msg: str, dataset_path: Optional[str] = None
) -> Optional[str]:
    """Try to heuristically extract a file path or filename from a validator message."""
    if not msg:
        return None

    # If message explicitly contains an absolute path
    abs_path_match = re.search(r"(/[^\s:,]+\.[A-Za-z0-9]+(?:\.gz)?)", msg)
    if abs_path_match:
        extracted = abs_path_match.group(1)
        return strip_temp_path(extracted, dataset_path)

    # dataset_description.json special case
    if "dataset_description.json" in msg:
        return "dataset_description.json"

    # Look for sub-... filenames like sub-01_task-foo_blah.ext
    name_match = re.search(r"(sub-[A-Za-z0-9._-]+\.[A-Za-z0-9]+(?:\.gz)?)", msg)
    if name_match:
        return name_match.group(1)

    # Generic filename with extension (e.g., task-recognition_stim.json)
    generic_match = re.search(
        r"([A-Za-z0-9._\-]+\.(?:json|tsv|edf|nii|nii\.gz|txt|csv|mp4|png|jpg|jpeg))",
        msg,
    )
    if generic_match:
        return generic_match.group(1)

    return None


def get_error_code_from_message(message: str) -> str:
    """Extract error code from validation message."""
    # Check for PRISM error codes first (new format)
    prism_match = re.search(r"(PRISM\d{3})", message)
    if prism_match:
        return prism_match.group(1)

    # Legacy error code detection
    if "Invalid BIDS filename" in message or "Invalid BIDS filename format" in message:
        return "PRISM101"  # INVALID_BIDS_FILENAME -> PRISM101
    elif "Missing sidecar" in message or "Missing sidecar for" in message:
        return "PRISM201"  # MISSING_SIDECAR -> PRISM201
    elif "schema error" in message:
        return "PRISM301"  # SCHEMA_VALIDATION_ERROR -> PRISM301
    elif "not valid JSON" in message or "is not valid JSON" in message:
        return "PRISM202"  # INVALID_JSON -> PRISM202
    elif "doesn't match expected pattern" in message:
        return "PRISM101"  # FILENAME_PATTERN_MISMATCH -> PRISM101

    return "PRISM999"  # GENERAL_ERROR


# Error descriptions using new PRISM codes
ERROR_DESCRIPTIONS = {
    "PRISM001": "Missing dataset_description.json file",
    "PRISM002": "No subjects found in dataset",
    "PRISM003": "Invalid dataset_description.json content",
    "PRISM101": "Filenames must follow BIDS naming convention (sub-<label>_[ses-<label>_]...)",
    "PRISM102": "Subject ID mismatch between filename and directory",
    "PRISM103": "Session ID mismatch between filename and directory",
    "PRISM201": "Required JSON sidecar files are missing for data files",
    "PRISM202": "JSON files contain syntax errors or are not valid JSON",
    "PRISM203": "Empty sidecar file",
    "PRISM301": "Missing required field in sidecar",
    "PRISM302": "Invalid field type in sidecar",
    "PRISM303": "Invalid field value in sidecar",
    "PRISM501": ".bidsignore needs update for PRISM compatibility",
    "PRISM900": "Plugin validation issue",
    "PRISM999": "General validation error",
    "EMPTY_DATASET": "Dataset contains no data files or all files were filtered as system files",
    # Legacy mappings for backwards compatibility
    "INVALID_BIDS_FILENAME": "Filenames must follow BIDS naming convention",
    "MISSING_SIDECAR": "Required JSON sidecar files are missing",
    "SCHEMA_VALIDATION_ERROR": "JSON sidecar content does not match required schema",
    "INVALID_JSON": "JSON files contain syntax errors",
    "FILENAME_PATTERN_MISMATCH": "Filenames do not match expected patterns",
    "GENERAL_ERROR": "Validation error",
}


def get_error_description(error_code: str) -> str:
    """Get user-friendly descriptions for error codes."""
    return ERROR_DESCRIPTIONS.get(error_code, "Validation error")


def get_error_documentation_url(error_code: str) -> str:
    """Get documentation URL for an error code."""
    base_url = "https://prism-validator.readthedocs.io/en/latest/ERROR_CODES.html"

    # Map legacy codes to PRISM codes for URL
    code_mapping = {
        "INVALID_BIDS_FILENAME": "prism101---invalid-filename-pattern",
        "MISSING_SIDECAR": "prism201---missing-sidecar",
        "SCHEMA_VALIDATION_ERROR": "prism301---missing-required-field",
        "INVALID_JSON": "prism202---invalid-json-syntax",
        "FILENAME_PATTERN_MISMATCH": "prism101---invalid-filename-pattern",
    }

    # PRISM code anchors
    if error_code.startswith("PRISM"):
        anchor = f"#{error_code.lower()}---"
        return f"{base_url}{anchor}"

    if error_code in code_mapping:
        return f"{base_url}#{code_mapping[error_code]}"

    return base_url


def shorten_path(file_path: str, max_parts: int = 3) -> str:
    """Shorten a file path to show only the last N parts with ellipsis."""
    if not file_path:
        return "General"

    parts = file_path.replace("\\", "/").split("/")
    if len(parts) <= max_parts:
        return "/".join(parts)

    return ".../" + "/".join(parts[-max_parts:])


def get_filename_from_path(file_path: str) -> str:
    """Extract just the filename from a path."""
    if not file_path:
        return "General"
    return os.path.basename(file_path)


def list_survey_template_languages(
    library_path: str,
) -> tuple[list[str], str | None, int, int]:
    """Return (languages, default_language, template_count, i18n_count) from survey templates in a folder.

    Args:
        library_path: Path to the survey template library folder

    Returns:
        Tuple of (sorted language list, default language, total template count, templates with I18n count)
    """
    from pathlib import Path
    import json

    langs: set[str] = set()
    defaults: set[str] = set()
    template_count = 0
    i18n_count = 0

    try:
        root = Path(library_path).resolve()
    except Exception:
        return [], None, 0, 0

    if not root.exists() or not root.is_dir():
        return [], None, 0, 0

    for p in sorted(root.glob("survey-*.json")):
        template_count += 1
        has_i18n = False

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        i18n = data.get("I18n")
        if isinstance(i18n, dict):
            i18n_langs = i18n.get("Languages")
            if isinstance(i18n_langs, list) and len(i18n_langs) > 0:
                has_i18n = True
                for v in i18n_langs:
                    if isinstance(v, str) and v.strip():
                        langs.add(v.strip())
            d = i18n.get("DefaultLanguage")
            if isinstance(d, str) and d.strip():
                defaults.add(d.strip())

        tech = data.get("Technical")
        if isinstance(tech, dict):
            tl = tech.get("Language")
            if isinstance(tl, str) and tl.strip():
                langs.add(tl.strip())

        if has_i18n:
            i18n_count += 1

    default = None
    if len(defaults) == 1:
        default = next(iter(defaults))

    return sorted(list(langs)), default, template_count, i18n_count


def sanitize_jsonable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable objects (like sets) to lists."""
    if isinstance(obj, dict):
        return {k: sanitize_jsonable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_jsonable(v) for v in obj]
    elif hasattr(obj, "__dict__"):
        return sanitize_jsonable(vars(obj))
    return obj


def format_validation_results(
    issues: list, dataset_stats: Any, dataset_path: str
) -> dict:
    """Format validation results in BIDS-validator style with grouped errors.

    Args:
        issues: List of validation issues (tuples or dicts)
        dataset_stats: Stats object from validator
        dataset_path: Path to the validated dataset

    Returns:
        Formatted results dictionary for web display
    """
    # Group issues by error code and type
    error_groups: Dict[str, Dict[str, Any]] = {}
    warning_groups: Dict[str, Dict[str, Any]] = {}

    valid_files = []
    invalid_files = []
    file_paths = set()

    for issue in issues:
        # Support tuples like (level, message) or (level, message, path)
        if isinstance(issue, dict):
            level = (
                issue.get("type")
                or issue.get("level")
                or issue.get("severity")
                or "ERROR"
            )
            message = issue.get("message", "")
            file_path = issue.get("file")
        elif isinstance(issue, (list, tuple)):
            if len(issue) >= 2:
                level, message = issue[0], issue[1]
                file_path = issue[2] if len(issue) > 2 else None
            else:
                continue
        else:
            level = "ERROR"
            message = str(issue)
            file_path = None

        # Always strip temp path from file_path
        if not file_path:
            file_path = extract_path_from_message(message, dataset_path)
        file_path = strip_temp_path(file_path, dataset_path) if file_path else None

        if file_path:
            file_paths.add(file_path)

        # Strip temp path from message text
        message = strip_temp_path_from_message(message)

        # Extract error code from message
        error_code = get_error_code_from_message(message)

        formatted_issue = {
            "code": error_code,
            "message": message,
            "file": file_path,
            "level": level,
        }

        if level == "ERROR":
            if error_code not in error_groups:
                error_groups[error_code] = {
                    "code": error_code,
                    "description": get_error_description(error_code),
                    "files": [],
                    "count": 0,
                    "messages": {}  # Group by message
                }
            
            # Add to message group
            if message not in error_groups[error_code]["messages"]:
                error_groups[error_code]["messages"][message] = []
            error_groups[error_code]["messages"][message].append(file_path)
            
            error_groups[error_code]["files"].append(formatted_issue)
            error_groups[error_code]["count"] += 1

            if file_path:
                invalid_files.append({"path": file_path, "errors": [message]})

        elif level == "WARNING":
            if error_code not in warning_groups:
                warning_groups[error_code] = {
                    "code": error_code,
                    "description": get_error_description(error_code),
                    "files": [],
                    "count": 0,
                    "messages": {}  # Group by message
                }
            
            # Add to message group
            if message not in warning_groups[error_code]["messages"]:
                warning_groups[error_code]["messages"][message] = []
            warning_groups[error_code]["messages"][message].append(file_path)
            
            warning_groups[error_code]["files"].append(formatted_issue)
            warning_groups[error_code]["count"] += 1

            if file_path:
                valid_files.append(
                    {"path": file_path}
                )  # Warnings don't make files invalid
        else:
            # Treat other levels as info/valid
            if file_path:
                valid_files.append({"path": file_path})

    # Calculate file counts
    try:
        stats_total = getattr(dataset_stats, "total_files", 0)
    except Exception:
        stats_total = 0

    if stats_total:
        total_files = stats_total
    else:
        total_files = (
            len(file_paths) if file_paths else len(valid_files) + len(invalid_files)
        )
        
    # Fallback: if still 0, count files on disk (excluding system files)
    if total_files == 0 and dataset_path and os.path.exists(dataset_path):
        disk_files = 0
        for root, dirs, files in os.walk(dataset_path):
            for f in files:
                if not is_system_file(f) and f != ".upload_manifest.json":
                    disk_files += 1
        total_files = disk_files

    # Add error if no files found
    if total_files == 0:
        error_code = "EMPTY_DATASET"
        if error_code not in error_groups:
            error_groups[error_code] = {
                "code": error_code,
                "description": "Dataset contains no data files",
                "files": [],
                "count": 0,
            }

        empty_dataset_issue = {
            "code": error_code,
            "message": "No data files found in dataset. Dataset may be empty or all files were filtered out as system files.",
            "file": dataset_path,
            "level": "ERROR",
        }
        error_groups[error_code]["files"].append(empty_dataset_issue)
        error_groups[error_code]["count"] += 1

    # Calculate summary
    total_errors = sum(group["count"] for group in error_groups.values())
    total_warnings = sum(group["count"] for group in warning_groups.values())

    # Count valid vs invalid files
    invalid_file_paths = {f["path"] for f in invalid_files if f.get("path")}
    invalid_count = len(invalid_file_paths)

    if stats_total:
        valid_count = max(0, stats_total - invalid_count)
    else:
        valid_count = total_files - invalid_count

    # A dataset is valid only if it has no errors AND has at least some files
    is_valid = total_errors == 0 and total_files > 0

    # Try to get dataset name from dataset_description.json
    dataset_name = os.path.basename(dataset_path)
    try:
        desc_path = os.path.join(dataset_path, "dataset_description.json")
        if os.path.exists(desc_path):
            with open(desc_path, "r") as f:
                desc_data = json.load(f)
                if "Name" in desc_data:
                    dataset_name = desc_data["Name"]
    except Exception:
        pass

    # Convert dataset_stats to a serializable dict if it's a DatasetStats object
    serializable_stats = {}
    if dataset_stats:
        if hasattr(dataset_stats, "subjects"):
            # Calculate unique session labels
            session_entries = getattr(dataset_stats, "sessions", set()) or set()
            unique_sessions = set()
            for entry in session_entries:
                if isinstance(entry, str) and "/" in entry:
                    unique_sessions.add(entry.split("/", 1)[1])
                elif entry:
                    unique_sessions.add(entry)

            serializable_stats = {
                "total_subjects": len(getattr(dataset_stats, "subjects", [])),
                "total_sessions": len(unique_sessions),
                "modalities": getattr(dataset_stats, "modalities", {}),
                "tasks": sorted(list(getattr(dataset_stats, "tasks", []))),
                "surveys": sorted(list(getattr(dataset_stats, "surveys", []))),
                "biometrics": sorted(list(getattr(dataset_stats, "biometrics", []))),
                "total_files": getattr(dataset_stats, "total_files", 0),
                "sidecar_files": getattr(dataset_stats, "sidecar_files", 0),
            }
        elif isinstance(dataset_stats, dict):
            serializable_stats = dataset_stats

    return {
        "valid": is_valid,
        "summary": {
            "total_files": total_files,
            "valid_files": valid_count,
            "invalid_files": invalid_count,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        },
        "error_groups": error_groups,
        "warning_groups": warning_groups,
        "valid_files": valid_files,
        "invalid_files": invalid_files,
        "errors": [item for group in error_groups.values() for item in group["files"]],
        "warnings": [
            item for group in warning_groups.values() for item in group["files"]
        ],
        "dataset_path": dataset_path,
        "dataset_name": dataset_name,
        "dataset_stats": serializable_stats,
    }
