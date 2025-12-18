"""
Upload processing for prism-validator web interface.
Handles folder uploads, ZIP extraction, and placeholder creation.
"""

import os
import json
import zipfile
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple, Set

from .utils import is_system_file


# File extensions to process (metadata and small data files only)
METADATA_EXTENSIONS = {
    ".json",  # Sidecar metadata
    ".tsv",   # Behavioral/events data
    ".csv",   # Alternative tabular format
    ".txt",   # Text data/logs
    ".edf",   # EEG/eye-tracking (relatively small)
    ".bdf",   # BioSemi EEG format
    ".png",
    ".jpg",
    ".jpeg",  # Stimulus images
}

# Extensions to SKIP (large data files we don't need)
SKIP_EXTENSIONS = {
    ".nii",
    ".nii.gz",  # NIfTI neuroimaging
    ".mp4",
    ".avi",
    ".mov",  # Video files
    ".tiff",  # Large TIFF images
    ".eeg",
    ".dat",
    ".fif",  # Large electrophysiology
    ".mat",  # MATLAB files
}

# Names that indicate BIDS modality folders (should not be stripped)
RESTRICTED_FOLDER_NAMES = {
    "image",
    "audio",
    "movie",
    "survey",
    "eyetracking",
    "physiological",
    "physio",
    "eeg",
    "func",
    "anat",
    "dwi",
    "fmap",
    "events",
    "biometrics",
    "dataset",
}


def detect_dataset_prefix(all_paths: List[str]) -> Optional[str]:
    """Detect a common leading folder that should be stripped from uploaded paths.
    
    Returns the folder name to strip, or None if no prefix should be stripped.
    """
    sanitized_parts = []
    has_root_level_files = False
    
    for path in all_paths or []:
        if not path:
            continue
        parts = [part for part in path.replace("\\", "/").split("/") if part]
        if not parts:
            continue
        if len(parts) == 1:
            has_root_level_files = True
        sanitized_parts.append(parts)
    
    # If there are root-level files, don't strip anything
    if has_root_level_files or not sanitized_parts:
        return None
    
    # Check if all paths start with the same folder
    first_components = {parts[0] for parts in sanitized_parts}
    if len(first_components) != 1:
        return None
    
    candidate = first_components.pop()
    
    # Don't strip if it looks like a BIDS folder
    if candidate.startswith(("sub-", "ses-")) or candidate.lower() in RESTRICTED_FOLDER_NAMES:
        return None
    
    # Only strip if it contains dataset structure
    has_dataset_description = any(
        len(parts) >= 2
        and parts[0] == candidate
        and parts[1] == "dataset_description.json"
        for parts in sanitized_parts
    )
    has_subject_dirs = any(
        len(parts) >= 2 and parts[0] == candidate and parts[1].startswith("sub-")
        for parts in sanitized_parts
    )
    
    if not (has_dataset_description or has_subject_dirs):
        return None
    
    return candidate


def normalize_relative_path(path: str, prefix_to_strip: Optional[str]) -> Optional[str]:
    """Normalize an uploaded path to be relative to the dataset root.
    
    Args:
        path: The uploaded file path
        prefix_to_strip: Optional folder prefix to remove
        
    Returns:
        Normalized path, or None if path is invalid
    """
    if not path:
        return None
    
    cleaned = path.replace("\\", "/").lstrip("/")
    
    if prefix_to_strip:
        prefix = prefix_to_strip.strip("/")
        if cleaned.startswith(prefix + "/"):
            cleaned = cleaned[len(prefix) + 1:]
    
    normalized = os.path.normpath(cleaned)
    normalized = normalized.replace("\\", "/")
    
    if normalized in ("", "."):  # Directory only
        return None
    if normalized.startswith(".."):
        return None
    
    return normalized


def create_placeholder_content(file_path: str, extension: str) -> str:
    """Create informative placeholder content for data files (DataLad-style).
    
    Args:
        file_path: Original file path
        extension: File extension
        
    Returns:
        Placeholder content string
    """
    filename = os.path.basename(file_path)

    # For JSON files, create valid JSON placeholders
    if extension.lower() == ".json":
        return json.dumps(
            {
                "_placeholder": True,
                "_upload_mode": "DataLad-style (structure + metadata only)",
                "_original_filename": filename,
                "_created": datetime.now().isoformat(),
                "_note": "This is a placeholder file. Original JSON was not uploaded to reduce transfer size.",
            },
            indent=2,
        )

    # For TSV files, create valid TSV placeholders
    elif extension.lower() == ".tsv":
        return f"# PLACEHOLDER TSV - DataLad-style Upload\n# Original filename: {filename}\n# Created: {datetime.now().isoformat()}\n_placeholder\ttrue\n"

    # For other file types, use text placeholder
    else:
        file_type_map = {
            ".nii": "NIfTI neuroimaging data",
            ".nii.gz": "Compressed NIfTI neuroimaging data",
            ".png": "PNG image stimulus",
            ".jpg": "JPEG image stimulus",
            ".jpeg": "JPEG image stimulus",
            ".tiff": "TIFF image data",
            ".mp4": "MP4 video stimulus",
            ".avi": "AVI video data",
            ".mov": "QuickTime video",
            ".eeg": "EEG raw data",
            ".dat": "Binary data file",
            ".fif": "Neuromag/MNE data",
            ".mat": "MATLAB data file",
            ".edf": "European Data Format (EEG/Physio)",
            ".bdf": "BioSemi Data Format",
            ".set": "EEGLAB dataset info",
            ".fdt": "EEGLAB data file",
        }

        file_type = file_type_map.get(extension, f"{extension} data file")

        return f"""# PLACEHOLDER FILE - DataLad-style Upload
# This is a placeholder for the original data file that was not uploaded
# to reduce transfer size and processing time.

Original filename: {filename}
File type: {file_type}
Upload mode: Structure-only validation
Created: {datetime.now().isoformat()}

# The validator can still check:
# - File naming conventions
# - Directory structure
# - Metadata completeness (via JSON sidecars)
# - BIDS compliance

# Note: Full content validation requires the complete dataset.
"""


def process_folder_upload(
    files: list,
    temp_dir: str,
    metadata_paths: Optional[List[str]] = None,
    all_files_list: Optional[List[str]] = None,
) -> Tuple[str, dict]:
    """Process uploaded folder files and recreate directory structure (DataLad-style).
    
    DataLad-inspired approach: Upload only structure and metadata, create placeholders
    for large data files. This allows full dataset validation without transferring GB of data.
    
    Args:
        files: List of uploaded file objects
        temp_dir: Temporary directory to store files
        metadata_paths: Optional list of paths for uploaded files
        all_files_list: Optional list of all file paths (including skipped ones)
        
    Returns:
        Tuple of (dataset_root path, manifest dict)
    """
    dataset_root = os.path.join(temp_dir, "dataset")
    os.makedirs(dataset_root, exist_ok=True)

    processed_count = 0
    skipped_count = 0
    manifest = {
        "uploaded_files": [],
        "placeholder_files": [],
        "upload_type": "structure_only",
        "timestamp": datetime.now().isoformat(),
    }

    metadata_paths = metadata_paths or []
    all_files_list = all_files_list or []

    # Detect prefix to strip
    candidate_paths = list(all_files_list or [])
    if metadata_paths:
        candidate_paths.extend(metadata_paths)
    else:
        candidate_paths.extend(
            [f.filename for f in files if getattr(f, "filename", None)]
        )

    prefix_to_strip = detect_dataset_prefix(candidate_paths)
    if prefix_to_strip:
        print(f"📁 [UPLOAD] Stripping leading folder: {prefix_to_strip}")

    # Track uploaded file paths
    uploaded_paths: Set[str] = set()

    # Process uploaded files
    for index, file in enumerate(files):
        original_path = (
            metadata_paths[index]
            if index < len(metadata_paths)
            else getattr(file, "filename", "")
        )
        if not original_path:
            continue
        
        normalized_path = normalize_relative_path(original_path, prefix_to_strip)
        if not normalized_path:
            continue

        # Skip system files
        filename = os.path.basename(normalized_path)
        if is_system_file(filename):
            continue

        uploaded_paths.add(normalized_path)
        file_path = os.path.join(dataset_root, *normalized_path.split("/"))
        target_dir = os.path.dirname(file_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        file.save(file_path)
        processed_count += 1

        manifest["uploaded_files"].append({
            "path": normalized_path,
            "size": file.content_length or 0,
            "type": "metadata",
        })

    # Create smart placeholders for non-uploaded files
    for relative_path in all_files_list:
        normalized_path = normalize_relative_path(relative_path, prefix_to_strip)
        if not normalized_path or normalized_path in uploaded_paths:
            continue

        filename = os.path.basename(normalized_path)
        if is_system_file(filename):
            continue

        file_path = os.path.join(dataset_root, *normalized_path.split("/"))
        target_dir = os.path.dirname(file_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        lower_path = normalized_path.lower()
        if lower_path.endswith(".nii.gz"):
            ext = ".nii.gz"
        else:
            _, ext = os.path.splitext(lower_path)
        
        placeholder_content = create_placeholder_content(normalized_path, ext)
        with open(file_path, "w") as f:
            f.write(placeholder_content)
        skipped_count += 1

        manifest["placeholder_files"].append({
            "path": normalized_path,
            "extension": ext,
            "type": "placeholder",
        })

    # Save manifest
    manifest_path = os.path.join(dataset_root, ".upload_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"📁 Processed {processed_count} metadata files, created {skipped_count} placeholders")
    
    return dataset_root, manifest


def process_zip_upload(file, temp_dir: str, filename: str) -> str:
    """Process uploaded ZIP file.
    
    Extracts only metadata files from ZIP to reduce processing time and storage.
    
    Args:
        file: Uploaded file object
        temp_dir: Temporary directory
        filename: Secure filename
        
    Returns:
        Dataset root path
    """
    file_path = os.path.join(temp_dir, filename)
    file.save(file_path)

    processed_count = 0
    skipped_count = 0

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        for zip_info in zip_ref.namelist():
            # Skip directories
            if zip_info.endswith("/"):
                continue

            # Check file extension
            _, ext = os.path.splitext(zip_info.lower())
            if ext == ".gz" and zip_info.lower().endswith(".nii.gz"):
                ext = ".nii.gz"

            # Extract metadata files, skip large data files
            if ext in METADATA_EXTENSIONS or ext == "":
                zip_ref.extract(zip_info, temp_dir)
                processed_count += 1
            elif ext in SKIP_EXTENSIONS:
                # Create empty placeholder
                extract_path = os.path.join(temp_dir, zip_info)
                os.makedirs(os.path.dirname(extract_path), exist_ok=True)
                with open(extract_path, "w") as f:
                    f.write("")
                skipped_count += 1

    print(f"📦 Extracted {processed_count} metadata files, skipped {skipped_count} data files")

    return find_dataset_root(temp_dir)


def find_dataset_root(extract_dir: str) -> str:
    """Find the actual dataset root directory after extraction.
    
    Args:
        extract_dir: Directory where files were extracted
        
    Returns:
        Path to the dataset root
    """
    # Look for dataset_description.json or typical BIDS structure
    for root, dirs, files in os.walk(extract_dir):
        if "dataset_description.json" in files:
            return root
        if any(d.startswith("sub-") for d in dirs):
            return root

    return extract_dir
