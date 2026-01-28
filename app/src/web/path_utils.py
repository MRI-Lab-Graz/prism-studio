"""
Path manipulation utilities for PRISM web interface.
"""

import os
import re
from typing import Optional


def strip_temp_path(
    file_path: str, dataset_path: Optional[str] = None
) -> Optional[str]:
    """Strip temporary folder path prefix and keep only relative path from dataset root."""
    if not file_path:
        return None

    # Normalize separators
    file_path = file_path.replace("\\", "/")

    # If dataset_path is provided, try to strip up to its parent folder
    # This keeps the dataset root folder name (e.g., messy_dataset/sub-01)
    if dataset_path:
        dataset_path = dataset_path.replace("\\", "/").rstrip("/")
        parent_dir = os.path.dirname(dataset_path)
        if parent_dir and parent_dir != "/":
            prefix = parent_dir if parent_dir.endswith("/") else parent_dir + "/"
            if file_path.startswith(prefix):
                return file_path[len(prefix) :]
            elif prefix in file_path:
                idx = file_path.find(prefix)
                return file_path[idx + len(prefix) :]

        # Fallback to stripping the dataset_path itself
        ds_prefix = dataset_path + "/"
        if file_path.startswith(ds_prefix):
            return file_path[len(ds_prefix) :]
        elif dataset_path in file_path:
            idx = file_path.find(dataset_path)
            return file_path[idx + len(dataset_path) :].lstrip("/")

    # Look for common BIDS/PRISM root markers
    markers = [
        "sub-",
        "dataset_description.json",
        "participants.tsv",
        "task-",
        "survey-",
    ]
    best_match = None
    for marker in markers:
        if marker in file_path:
            idx = file_path.find(marker)
            match_path = file_path[idx:]
            if not best_match or len(match_path) > len(best_match):
                best_match = match_path

    if best_match:
        return best_match

    # If it's a temp path, try to extract the relative path
    # Unix: /tmp/, /var/folders/, /T/
    # Windows: C:\Users\...\AppData\Local\Temp\, C:\Temp\, etc.
    temp_patterns = [
        "/tmp/",
        "/T/prism_validator_",
        "/var/folders/",
        "prism_validator_",
        "renamed_files",
        "/Temp/",
        "\\Temp\\",
        "\\AppData\\",
    ]
    if any(p in file_path for p in temp_patterns):
        if "/dataset/" in file_path or "\\dataset\\" in file_path:
            # Handle both Unix and Windows separators
            parts = file_path.replace("\\", "/").split("/dataset/", 1)
            if len(parts) > 1:
                return parts[1]

        if "renamed_files" in file_path:
            idx = file_path.rfind("renamed_files")
            slash_idx = file_path.find(os.sep, idx)
            if slash_idx != -1:
                return file_path[slash_idx + 1 :]

        parts = [p for p in file_path.split(os.sep) if p]
        if len(parts) >= 2:
            if parts[-2].startswith("sub-") or parts[-2] in [
                "physio",
                "anat",
                "func",
                "survey",
                "eyetracking",
                "dwi",
                "fmap",
            ]:
                return os.sep.join(parts[-2:])
        if len(parts) >= 1:
            return parts[-1]

    return file_path


def strip_temp_path_from_message(msg: str, dataset_path: Optional[str] = None) -> str:
    """Remove temp folder paths from message text."""
    if not msg:
        return msg

    msg = msg.replace("\\", "/")

    # If dataset_path is provided, try to strip up to its parent folder
    # This keeps the dataset root folder name (e.g., /messy_dataset/sub-01)
    did_dataset_strip = False
    if dataset_path:
        dataset_path = dataset_path.replace("\\", "/").rstrip("/")
        parent_dir = os.path.dirname(dataset_path)
        if parent_dir and parent_dir != "/":
            prefix = parent_dir if parent_dir.endswith("/") else parent_dir + "/"
            if prefix in msg:
                msg = msg.replace(prefix, "/")
                did_dataset_strip = True

        # Fallback: strip the dataset_path itself if parent stripping didn't work/apply
        ds_prefix = dataset_path + "/"
        if ds_prefix in msg:
            msg = msg.replace(ds_prefix, "")
            did_dataset_strip = True

    # Normalize multiple slashes that might have been created
    msg = msg.replace("//", "/")

    # Only apply heuristic marker-based stripping if we didn't do a dataset strip
    # or if the message STILL contains absolute system markers
    # Check for both Unix (/var, /tmp) and Windows (C:\Users\AppData, \Temp) paths
    has_system_markers = any(
        p in msg
        for p in [
            "/var/folders/",
            "/tmp/prism_",
            "/prism_validator_",
            "\\AppData\\",
            "\\Temp\\",
            "C:\\Users",
        ]
    )

    if not did_dataset_strip or has_system_markers:
        markers = [
            "sub-",
            "dataset_description.json",
            "participants.tsv",
            "task-",
            "survey-",
        ]
        for marker in markers:
            if marker in msg:
                # Only strip automatically if it looks like a temporary or absolute path
                # This pattern matches common Unix absolute roots and temp folders
                temp_prefix_pattern = (
                    r"/(?:var|tmp|Volumes|Users|home|Users|prism_validator|renamed_files)[^\s,:]*/"
                    + re.escape(marker)
                )
                msg = re.sub(temp_prefix_pattern, marker, msg)

                # Legacy fallback for renamed_files
                renamed_pattern = r"renamed_files[^/\s,:]*/" + re.escape(marker)
                msg = re.sub(renamed_pattern, marker, msg)

    # Patterns for Unix and Windows temp paths
    temp_patterns = [
        r"/var/folders/[^/\s,:]+/[^/\s,:]+/T/prism_validator_[^/\s,:]+/",
        r"/tmp/prism_validator_[^/\s,:]+/",
        r"prism_validator_[^/\s,:]+/",
        r"renamed_files[^/\s,:]*/",
        r"[A-Z]:\\\\Users\\\\[^\\\\\s,:]+\\\\AppData\\\\Local\\\\Temp\\\\[^\\\\\s,:]+\\\\",  # Windows temp
        r"[A-Z]:\\\\Temp\\\\[^\\\\\s,:]+\\\\",  # Alternative Windows temp
    ]

    for pattern in temp_patterns:
        msg = re.sub(pattern, "", msg)

    return msg.strip()


def extract_path_from_message(
    msg: str, dataset_path: Optional[str] = None
) -> Optional[str]:
    """Try to heuristically extract a file path or filename from a validator message."""
    if not msg:
        return None

    abs_path_match = re.search(r"(/[^\s:,]+\.[A-Za-z0-9]+(?:\.gz)?)", msg)
    if abs_path_match:
        return strip_temp_path(abs_path_match.group(1), dataset_path)

    if "dataset_description.json" in msg:
        return "dataset_description.json"

    name_match = re.search(r"((?:sub|ses)-[A-Za-z0-9._-]+\.[A-Za-z0-9]+(?:\.gz)?)", msg)
    if name_match:
        return name_match.group(1)

    generic_match = re.search(
        r"([A-Za-z0-9._\-]+\.(?:json|tsv|edf|nii|nii\.gz|txt|csv|mp4|png|jpg|jpeg|bval|bvec|vhdr|vmrk|eeg|dat|fif))",
        msg,
    )
    if generic_match:
        return generic_match.group(1)

    return None


def shorten_path(file_path: str, max_parts: int = 3) -> str:
    """Shorten a file path to show only the last N parts with ellipsis."""
    if not file_path:
        return "General"

    parts = file_path.replace("\\", os.sep).split(os.sep)
    if len(parts) <= max_parts:
        return os.sep.join(parts)

    return "..." + os.sep + os.sep.join(parts[-max_parts:])


def get_filename_from_path(file_path: str) -> str:
    """Extract just the filename from a path."""
    if not file_path:
        return "General"
    return os.path.basename(file_path)
