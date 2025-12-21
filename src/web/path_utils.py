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

    # Look for common BIDS/PRISM root markers
    markers = ["sub-", "dataset_description.json", "participants.tsv", "task-", "survey-"]
    best_match = None
    for marker in markers:
        if marker in file_path:
            idx = file_path.find(marker)
            match_path = file_path[idx:]
            if not best_match or len(match_path) > len(best_match):
                best_match = match_path
    
    if best_match:
        return best_match

    # If dataset_path is a temp directory, strip it
    if dataset_path:
        dataset_path = dataset_path.replace("\\", "/")
        ds_prefix = dataset_path if dataset_path.endswith("/") else dataset_path + "/"
        if file_path.startswith(ds_prefix):
            return file_path[len(ds_prefix) :]
        elif dataset_path in file_path:
            idx = file_path.find(dataset_path)
            return file_path[idx + len(dataset_path) :].lstrip("/")

    # If it's a temp path, try to extract the relative path
    temp_patterns = ["/tmp/", "/T/prism_validator_", "/var/folders/", "prism_validator_", "renamed_files"]
    if any(p in file_path for p in temp_patterns):
        if "/dataset/" in file_path:
            parts = file_path.split("/dataset/", 1)
            if len(parts) > 1:
                return parts[1]
        
        if "renamed_files" in file_path:
            idx = file_path.rfind("renamed_files")
            slash_idx = file_path.find("/", idx)
            if slash_idx != -1:
                return file_path[slash_idx + 1:]
        
        parts = [p for p in file_path.split("/") if p]
        if len(parts) >= 2:
            if parts[-2].startswith("sub-") or parts[-2] in ["physio", "anat", "func", "survey", "eyetracking", "dwi", "fmap"]:
                return "/".join(parts[-2:])
        if len(parts) >= 1:
            return parts[-1]

    return file_path


def strip_temp_path_from_message(msg: str) -> str:
    """Remove temp folder paths from message text."""
    if not msg:
        return msg
    
    msg = msg.replace("\\", "/")
    markers = ["sub-", "dataset_description.json", "participants.tsv", "task-", "survey-"]
    for marker in markers:
        if marker in msg:
            pattern = r"/[^\s,:]*/" + re.escape(marker)
            msg = re.sub(pattern, marker, msg)
            temp_prefix_pattern = r"(?:prism_validator|renamed_files)[^/\s,:]*" + re.escape(marker)
            msg = re.sub(temp_prefix_pattern, marker, msg)

    temp_patterns = [
        r"/var/folders/[^/\s,:]+/[^/\s,:]+/T/prism_validator_[^/\s,:]+/",
        r"/tmp/prism_validator_[^/\s,:]+/",
        r"prism_validator_[^/\s,:]+/",
        r"renamed_files[^/\s,:]*/"
    ]
    
    for pattern in temp_patterns:
        msg = re.sub(pattern, "", msg)
    
    return msg.replace("dataset/", "").strip()


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

    parts = file_path.replace("\\", "/").split("/")
    if len(parts) <= max_parts:
        return "/".join(parts)

    return ".../" + "/".join(parts[-max_parts:])


def get_filename_from_path(file_path: str) -> str:
    """Extract just the filename from a path."""
    if not file_path:
        return "General"
    return os.path.basename(file_path)
