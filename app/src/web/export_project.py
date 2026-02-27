"""
Project export functionality with anonymization support.

This module provides utilities for exporting entire PRISM projects
with optional anonymization of participant IDs and copyright-protected content.
"""

import os
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Set


def anonymize_filename(filename: str, mapping: Dict[str, str]) -> str:
    """
    Replace participant IDs in filenames using the mapping.

    Args:
        filename: Original filename (e.g., "sub-001_ses-01_task-stroop_eeg.tsv")
        mapping: Dict mapping original_id → random_id

    Returns:
        Anonymized filename
    """
    result = filename
    for original_id, random_id in mapping.items():
        # Replace in filename
        result = result.replace(original_id, random_id)
    return result


def anonymize_json_file(
    json_path: Path, output_path: Path, mask_questions: bool = True
) -> None:
    """
    Anonymize a JSON sidecar file by stripping question descriptions.

    Args:
        json_path: Input JSON file
        output_path: Output JSON file
        mask_questions: Whether to mask question text
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if mask_questions and isinstance(data, dict):
        # List of metadata keys that should NOT be masked
        metadata_keys = {
            "Technical",
            "Study",
            "Metadata",
            "I18n",
            "Normative",
            "Items",
            "SchemaVersion",
            "Version",
            "License",
            "Citation",
        }

        # Counter for generic labels
        question_num = 1

        # Iterate through all top-level keys
        for key in list(data.keys()):
            # Skip metadata keys
            if key in metadata_keys:
                continue

            item = data[key]

            # Check if this looks like a survey item (has Description or Levels)
            if isinstance(item, dict) and ("Description" in item or "Levels" in item):
                # Replace description with generic label
                if "Description" in item:
                    item["Description"] = f"Question {question_num}"

                # Also mask QuestionText if present
                if "QuestionText" in item:
                    item["QuestionText"] = "[MASKED]"

                question_num += 1

        # Also handle old-style "Items" array format (if present)
        if "Items" in data and isinstance(data["Items"], list):
            for idx, item in enumerate(data["Items"], start=1):
                if isinstance(item, dict):
                    if "Description" in item:
                        item["Description"] = {"en": f"Question {idx}"}
                    if "QuestionText" in item:
                        item["QuestionText"] = {"en": "[MASKED]"}

    # Write anonymized JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def anonymize_tsv_file(
    tsv_path: Path, output_path: Path, participant_mapping: Dict[str, str]
) -> None:
    """
    Anonymize a TSV file by replacing participant IDs.

    Args:
        tsv_path: Input TSV file
        output_path: Output TSV file
        participant_mapping: Dict mapping original_id → random_id
    """
    import csv

    with open(tsv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = list(reader)

    # Update participant IDs
    for row in rows:
        for id_field in ["participant_id", "subject_id", "sub"]:
            if id_field in row and row[id_field]:
                original = row[id_field]
                row[id_field] = participant_mapping.get(original, original)

    # Write anonymized file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=header, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def collect_participant_ids(project_path: Path) -> Set[str]:
    """
    Collect all participant IDs from a project.

    Args:
        project_path: Path to PRISM project

    Returns:
        Set of participant IDs
    """
    participant_ids = set()

    # Check participants.tsv at project root
    participants_file = project_path / "participants.tsv"
    if participants_file.exists():
        import csv

        with open(participants_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                pid = row.get("participant_id", "")
                if pid:
                    participant_ids.add(pid)

    for item in project_path.iterdir():
        if item.is_dir() and item.name.startswith("sub-"):
            participant_ids.add(item.name)

    return participant_ids


def export_project(
    project_path: Path,
    output_zip: Path,
    anonymize: bool = True,
    mask_questions: bool = True,
    id_length: int = 8,
    deterministic: bool = True,
    include_derivatives: bool = True,
    include_code: bool = True,
    include_analysis: bool = False,
) -> Dict[str, any]:
    """
    Export a PRISM project as a ZIP file with optional anonymization.

    Args:
        project_path: Path to PRISM project
        output_zip: Path for output ZIP file
        anonymize: Whether to randomize participant IDs
        mask_questions: Whether to mask copyrighted question text
        id_length: Length of random ID part
        deterministic: Use deterministic random ID generation
        include_derivatives: Include derivatives/ folder
        include_code: Include code/ folder
        include_analysis: Include analysis/ folder

    Returns:
        Dict with export statistics
    """
    from src.anonymizer import create_participant_mapping

    # Create temporary directory for preparing export
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        export_root = temp_path / "project_export"
        export_root.mkdir()

        # Collect participant IDs if anonymization is enabled
        participant_mapping = {}
        if anonymize:
            participant_ids = collect_participant_ids(project_path)
            if participant_ids:
                mapping_file = temp_path / "participants_mapping.json"
                participant_mapping = create_participant_mapping(
                    list(participant_ids),
                    mapping_file,
                    id_length=id_length,
                    deterministic=deterministic,
                )
                print(
                    f"✓ Created anonymization mapping for {len(participant_mapping)} participants"
                )

        # Define what to copy
        folders_to_copy = {
            "derivatives": include_derivatives,
            "code": include_code,
            "analysis": include_analysis,
        }

        # Copy and anonymize folders
        stats = {
            "files_processed": 0,
            "files_anonymized": 0,
            "participant_count": len(participant_mapping),
        }

        def copy_folder_tree(source_folder: Path, dest_folder: Path) -> None:
            # Walk through source folder
            for root, dirs, files in os.walk(source_folder):
                rel_root = Path(root).relative_to(source_folder)

                # Create destination directory
                dest_dir = dest_folder / rel_root

                # Anonymize directory name if needed
                if anonymize and participant_mapping:
                    dest_dir_str = str(dest_dir)
                    for orig_id, anon_id in participant_mapping.items():
                        dest_dir_str = dest_dir_str.replace(orig_id, anon_id)
                    dest_dir = Path(dest_dir_str)

                dest_dir.mkdir(parents=True, exist_ok=True)

                # Process files
                for filename in files:
                    source_file = Path(root) / filename
                    stats["files_processed"] += 1

                    # Anonymize filename if needed
                    dest_filename = filename
                    if anonymize and participant_mapping:
                        dest_filename = anonymize_filename(
                            filename, participant_mapping
                        )
                        if dest_filename != filename:
                            stats["files_anonymized"] += 1

                    dest_file = dest_dir / dest_filename

                    # Process based on file type
                    if filename.endswith(".json"):
                        anonymize_json_file(source_file, dest_file, mask_questions)
                        if mask_questions:
                            stats["files_anonymized"] += 1
                    elif (
                        filename.endswith(".tsv") and anonymize and participant_mapping
                    ):
                        anonymize_tsv_file(source_file, dest_file, participant_mapping)
                        stats["files_anonymized"] += 1
                    else:
                        shutil.copy2(source_file, dest_file)

        for folder_name, should_include in folders_to_copy.items():
            if not should_include:
                continue

            source_folder = project_path / folder_name
            if not source_folder.exists():
                continue

            dest_folder = export_root / folder_name
            copy_folder_tree(source_folder, dest_folder)

        # Always include BIDS-style root-level subject folders
        for item in project_path.iterdir():
            if not (item.is_dir() and item.name.startswith("sub-")):
                continue

            dest_name = item.name
            if anonymize and participant_mapping:
                dest_name = anonymize_filename(dest_name, participant_mapping)
                if dest_name != item.name:
                    stats["files_anonymized"] += 1

            copy_folder_tree(item, export_root / dest_name)

        # Copy root-level files (README, dataset_description.json, etc.)
        root_files = [
            "participants.tsv",
            "participants.json",
            "README",
            "README.md",
            "README.txt",
            "CHANGES",
            "CHANGES.md",
            "LICENSE",
            "LICENSE.txt",
            "project.json",
            "contributors.json",
            "CITATION.cff",
        ]

        for filename in root_files:
            source_file = project_path / filename
            if source_file.exists():
                dest_file = export_root / filename
                if filename.endswith(".json"):
                    shutil.copy2(source_file, dest_file)
                else:
                    shutil.copy2(source_file, dest_file)
                stats["files_processed"] += 1

        # Create ZIP file
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(export_root):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(export_root)
                    zipf.write(file_path, arcname)

        print(f"✓ Export complete: {output_zip}")
        print(f"  Processed {stats['files_processed']} files")
        if anonymize:
            print(f"  Anonymized {stats['files_anonymized']} files/folders")
            print("  🔒 Mapping file is not included in ZIP export")

        return stats
