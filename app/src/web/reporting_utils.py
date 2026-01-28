"""
Reporting and formatting utilities for PRISM web interface.
"""

import os
import json
from typing import Any, Dict
from src.web.path_utils import (
    strip_temp_path,
    strip_temp_path_from_message,
    extract_path_from_message,
)
from src.issues import (
    get_error_description,
    get_fix_hint,
    get_error_documentation_url,
    infer_code_from_message,
)
from src.system_files import is_system_file


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
    """Format validation results in BIDS-validator style with grouped errors."""
    error_groups: Dict[str, Dict[str, Any]] = {}
    warning_groups: Dict[str, Dict[str, Any]] = {}

    # Track unique files and their issues to avoid double-counting and ensure correct categorization
    file_issues = {}  # path -> {errors: [], warnings: []}
    file_paths = set()

    for issue in issues:
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

        if not file_path:
            file_path = extract_path_from_message(message, dataset_path)
        file_path = strip_temp_path(file_path, dataset_path) if file_path else None

        message = strip_temp_path_from_message(message, dataset_path)

        if file_path:
            file_paths.add(file_path)
            if file_path not in file_issues:
                file_issues[file_path] = {"errors": [], "warnings": []}

            if level == "ERROR":
                file_issues[file_path]["errors"].append(message)
            elif level == "WARNING":
                file_issues[file_path]["warnings"].append(message)

        error_code = infer_code_from_message(message)

        group_message = message
        if ": " in message:
            parts = message.split(": ", 1)
            first_part = parts[0].lower()
            if (
                len(parts[0]) < 100
                and any(
                    m in first_part
                    for m in [
                        "sub-",
                        "ses-",
                        ".json",
                        ".tsv",
                        ".nii",
                        "dataset_description",
                    ]
                )
                and not any(
                    word in first_part
                    for word in [
                        "missing",
                        "potential",
                        "mislabeled",
                        "mixed",
                        "appears only",
                        "subject",
                        "session",
                    ]
                )
            ):
                group_message = parts[1]

        formatted_issue = {
            "code": error_code,
            "message": message,
            "file": file_path,
            "level": level,
        }

        target_groups = error_groups if level == "ERROR" else warning_groups
        if level in ["ERROR", "WARNING"]:
            if error_code not in target_groups:
                target_groups[error_code] = {
                    "code": error_code,
                    "description": get_error_description(error_code),
                    "fix_hint": get_fix_hint(error_code, message),
                    "documentation_url": get_error_documentation_url(error_code),
                    "files": [],
                    "count": 0,
                    "messages": {},
                }

            if group_message not in target_groups[error_code]["messages"]:
                target_groups[error_code]["messages"][group_message] = []
            target_groups[error_code]["messages"][group_message].append(file_path)

            target_groups[error_code]["files"].append(formatted_issue)
            target_groups[error_code]["count"] += 1

    # Categorize files for the UI lists
    invalid_files = []
    valid_files = []

    for path, data in file_issues.items():
        if data["errors"]:
            invalid_files.append({"path": path, "errors": data["errors"]})
        else:
            # Only include in valid_files list if it has warnings
            # (to avoid huge lists of perfectly fine files)
            if data["warnings"]:
                valid_files.append({"path": path, "warnings": data["warnings"]})

    try:
        stats_total = getattr(dataset_stats, "total_files", 0)
    except Exception:
        stats_total = 0

    total_files = stats_total or (
        len(file_paths) if file_paths else len(valid_files) + len(invalid_files)
    )

    if total_files == 0 and dataset_path and os.path.exists(dataset_path):
        disk_files = 0
        for root, dirs, files in os.walk(dataset_path):
            for f in files:
                if not is_system_file(f) and f != ".upload_manifest.json":
                    disk_files += 1
        total_files = disk_files

    if total_files == 0:
        error_code = "EMPTY_DATASET"
        if error_code not in error_groups:
            error_groups[error_code] = {
                "code": error_code,
                "description": "Dataset contains no data files",
                "files": [],
                "count": 0,
            }
        error_groups[error_code]["files"].append(
            {
                "code": error_code,
                "message": "No data files found in dataset.",
                "file": dataset_path,
                "level": "ERROR",
            }
        )
        error_groups[error_code]["count"] += 1

    total_errors = sum(group["count"] for group in error_groups.values())
    total_warnings = sum(group["count"] for group in warning_groups.values())

    # Differentiate between BIDS and PRISM
    bids_errors = sum(
        group["count"]
        for code, group in error_groups.items()
        if code.startswith("BIDS")
    )
    prism_errors = total_errors - bids_errors

    bids_warnings = sum(
        group["count"]
        for code, group in warning_groups.items()
        if code.startswith("BIDS")
    )
    prism_warnings = total_warnings - bids_warnings

    # Calculate invalid_count excluding the dataset root itself (global errors)
    dataset_root_name = os.path.basename(dataset_path) if dataset_path else ""
    invalid_file_paths = {f["path"] for f in invalid_files if f.get("path")}
    if dataset_root_name in invalid_file_paths:
        invalid_file_paths.remove(dataset_root_name)

    invalid_count = len(invalid_file_paths)
    valid_count = max(0, (stats_total or total_files) - invalid_count)
    is_valid = total_errors == 0 and total_files > 0

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

    serializable_stats = {}
    if dataset_stats:
        if hasattr(dataset_stats, "subjects"):
            session_entries = getattr(dataset_stats, "sessions", set()) or set()
            unique_sessions = {
                s.split("/", 1)[1] if "/" in s else s for s in session_entries if s
            }
            serializable_stats = {
                "total_subjects": len(getattr(dataset_stats, "subjects", [])),
                "total_sessions": len(unique_sessions),
                "modalities": getattr(dataset_stats, "modalities", {}),
                "tasks": sorted(list(getattr(dataset_stats, "tasks", []))),
                "func_tasks": sorted(list(getattr(dataset_stats, "func_tasks", []))),
                "eeg_tasks": sorted(list(getattr(dataset_stats, "eeg_tasks", []))),
                "eyetracking": sorted(list(getattr(dataset_stats, "eyetracking", []))),
                "physio": sorted(list(getattr(dataset_stats, "physio", []))),
                "surveys": sorted(list(getattr(dataset_stats, "surveys", []))),
                "biometrics": sorted(list(getattr(dataset_stats, "biometrics", []))),
                "total_files": getattr(dataset_stats, "total_files", 0),
                "sidecar_files": getattr(dataset_stats, "sidecar_files", 0),
            }
        elif isinstance(dataset_stats, dict):
            serializable_stats = dataset_stats

    # Prepare grouped results for the UI (BIDS-validator style)
    errors_list = []
    for group in error_groups.values():
        g = dict(group)
        g["message"] = g.get("description") or g.get("code")
        errors_list.append(g)

    warnings_list = []
    for group in warning_groups.values():
        g = dict(group)
        g["message"] = g.get("description") or g.get("code")
        warnings_list.append(g)

    return {
        "valid": is_valid,
        "summary": {
            "total_files": total_files,
            "valid_files": valid_count,
            "invalid_files": invalid_count,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "bids_errors": bids_errors,
            "prism_errors": prism_errors,
            "bids_warnings": bids_warnings,
            "prism_warnings": prism_warnings,
        },
        "error_groups": error_groups,
        "warning_groups": warning_groups,
        "valid_files": valid_files,
        "invalid_files": invalid_files,
        "errors": errors_list,
        "warnings": warnings_list,
        "dataset_path": dataset_path,
        "dataset_name": dataset_name,
        "dataset_stats": serializable_stats,
    }
