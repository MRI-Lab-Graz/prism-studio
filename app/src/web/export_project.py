"""
Project export functionality with anonymization support.

This module provides utilities for exporting entire PRISM projects
with optional anonymization of participant IDs and copyright-protected content.
"""

import os
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Set

from src.survey_scale_inference import get_survey_item_map


def _masked_like(value: Any, masked_text: str) -> Any:
    if isinstance(value, dict):
        masked = {str(key): masked_text for key in value.keys() if isinstance(key, str)}
        return masked or {"en": masked_text}
    return masked_text


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
    json_path: Path,
    output_path: Path,
    mask_questions: bool = True,
    participant_mapping: Optional[Dict[str, str]] = None,
) -> None:
    """
    Anonymize a JSON sidecar file.

    Applies participant ID replacement in all string values (covers IntendedFor
    and any other field embedding subject paths), then optionally masks survey
    question text.

    Args:
        json_path: Input JSON file
        output_path: Output JSON file
        mask_questions: Whether to mask survey question text
        participant_mapping: Dict mapping original_id → anonymised_id
    """
    from src.anonymizer import update_intendedfor_paths

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Replace participant IDs in all string values (IntendedFor etc.)
    if participant_mapping:
        data = update_intendedfor_paths(data, participant_mapping)

    if mask_questions and isinstance(data, dict):
        for question_num, item in enumerate(
            get_survey_item_map(data).values(), start=1
        ):
            if not isinstance(item, dict):
                continue
            if "Description" in item:
                item["Description"] = _masked_like(
                    item.get("Description"), f"Question {question_num}"
                )
            if "QuestionText" in item:
                item["QuestionText"] = _masked_like(
                    item.get("QuestionText"), "[MASKED]"
                )

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
    exclude_sessions: Optional[Set[str]] = None,
    exclude_modalities: Optional[Set[str]] = None,
    exclude_acq: Optional[Dict[str, Set[str]]] = None,
    scrub_mri_json: bool = False,
    progress_callback=None,
    cancelled_flag=None,
) -> Dict[str, Any]:
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
        progress_callback: Optional callable(percent, message) for progress updates
        cancelled_flag: Optional threading.Event; set it to request cancellation

    Returns:
        Dict with export statistics
    """
    from src.anonymizer import create_participant_mapping

    def _report(percent: int, message: str) -> None:
        if progress_callback:
            progress_callback(percent, message)

    def _check_cancelled() -> None:
        if cancelled_flag and cancelled_flag.is_set():
            raise InterruptedError("Export cancelled by user")

    _report(5, "Collecting participants...")
    _check_cancelled()

    participant_mapping = {}
    if anonymize:
        participant_ids = collect_participant_ids(project_path)
        if participant_ids:
            # Mapping is for internal use only; write to a throwaway temp file
            with tempfile.NamedTemporaryFile(
                suffix=".json", delete=False
            ) as mf:
                mapping_tmp = Path(mf.name)
            try:
                participant_mapping = create_participant_mapping(
                    list(participant_ids),
                    mapping_tmp,
                    id_length=id_length,
                    deterministic=deterministic,
                )
            finally:
                mapping_tmp.unlink(missing_ok=True)
            print(
                f"✓ Created anonymization mapping for {len(participant_mapping)} participants"
            )

    _report(10, "Scanning files...")
    _check_cancelled()

    # Decide which top-level folders to include
    folders_to_copy = {
        "derivatives": include_derivatives,
        "code": include_code,
        "analysis": include_analysis,
    }

    # Pre-count total files for accurate progress
    total_files = sum(
        len(files)
        for folder_name, should_include in folders_to_copy.items()
        if should_include and (project_path / folder_name).exists()
        for _, _, files in os.walk(project_path / folder_name)
    )
    total_files += sum(
        len(files)
        for item in project_path.iterdir()
        if item.is_dir() and item.name.startswith("sub-")
        for _, _, files in os.walk(item)
    )
    total_files = max(total_files, 1)

    stats: Dict[str, Any] = {
        "files_processed": 0,
        "files_anonymized": 0,
        "participant_count": len(participant_mapping),
    }

    def _anon_arc_path(rel_parts: list) -> str:
        """Apply participant-ID replacement to every component of an arc path."""
        if not (anonymize and participant_mapping):
            return str(Path(*rel_parts))
        parts = [anonymize_filename(p, participant_mapping) for p in rel_parts]
        return str(Path(*parts))

    def _json_bytes(source_file: Path) -> bytes:
        """Return (possibly anonymised/scrubbed) JSON as UTF-8 bytes, fully in-memory."""
        from src.anonymizer import update_intendedfor_paths

        with open(source_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if participant_mapping:
            data = update_intendedfor_paths(data, participant_mapping)
        if scrub_mri_json:
            from src.mri_json_scrubber import is_mri_json_sidecar, detect_modality_from_path, scrub_sensitive_json_fields
            if is_mri_json_sidecar(source_file):
                modality = detect_modality_from_path(source_file)
                data, _removed = scrub_sensitive_json_fields(data, modality=modality)
        if mask_questions and isinstance(data, dict):
            for question_num, item in enumerate(
                get_survey_item_map(data).values(), start=1
            ):
                if not isinstance(item, dict):
                    continue
                if "Description" in item:
                    item["Description"] = _masked_like(
                        item.get("Description"), f"Question {question_num}"
                    )
                if "QuestionText" in item:
                    item["QuestionText"] = _masked_like(
                        item.get("QuestionText"), "[MASKED]"
                    )
        return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")

    def _tsv_bytes(source_file: Path) -> bytes:
        """Return anonymised TSV as bytes, fully in-memory."""
        import csv
        import io

        with open(source_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            header = list(reader.fieldnames or [])
            rows = list(reader)
        for row in rows:
            for id_field in ["participant_id", "subject_id", "sub"]:
                if id_field in row and row[id_field]:
                    row[id_field] = participant_mapping.get(
                        row[id_field], row[id_field]
                    )
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=header, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    def _fmt_size(path: Path) -> str:
        """Return human-readable size of a file, or empty string if unavailable."""
        try:
            b = path.stat().st_size
            if b >= 1_073_741_824:
                return f"{b / 1_073_741_824:.1f} GB"
            if b >= 1_048_576:
                return f"{b / 1_048_576:.1f} MB"
            return f"{b / 1024:.0f} KB"
        except OSError:
            return ""

    def _add_tree(
        zipf: zipfile.ZipFile,
        source_root: Path,
        arc_prefix: str,
        skip_sessions: Optional[Set[str]] = None,
        skip_modalities: Optional[Set[str]] = None,
        skip_acq: Optional[Dict[str, Set[str]]] = None,
    ) -> None:
        """Walk source_root and write every file directly into zipf."""
        for root, _dirs, files in os.walk(source_root):
            _check_cancelled()
            rel_root = Path(root).relative_to(source_root)
            # Check if this path is under an excluded session or modality
            rel_parts = rel_root.parts
            if skip_sessions and rel_parts and rel_parts[0].startswith("ses-") and rel_parts[0] in skip_sessions:
                _dirs[:] = []  # prune subtree
                continue
            if skip_modalities:
                # modality is first part when no session, or second part when session present
                modality_part = rel_parts[1] if (len(rel_parts) > 1 and rel_parts[0].startswith("ses-")) else (rel_parts[0] if rel_parts else None)
                if modality_part and modality_part in skip_modalities:
                    _dirs[:] = []
                    continue
            # Determine current modality for acq filtering
            _cur_modality = None
            if rel_parts:
                _cur_modality = rel_parts[1] if (len(rel_parts) > 1 and rel_parts[0].startswith("ses-")) else rel_parts[0]
            for filename in files:
                # Keep participants mapping out of share ZIPs.
                if filename == "participants_mapping.json":
                    continue
                # Filter by acq- label if requested
                if skip_acq and _cur_modality and _cur_modality in skip_acq:
                    import re as _re
                    acq_m = _re.search(r"_acq-([A-Za-z0-9]+)", filename)
                    if acq_m and acq_m.group(1) in skip_acq[_cur_modality]:
                        continue
                source_file = Path(root) / filename
                stats["files_processed"] += 1

                # Build archive path with optional anonymisation
                parts = list(rel_parts) + [filename]
                arc_rel = _anon_arc_path(parts)
                arcname = f"{arc_prefix}/{arc_rel}" if arc_prefix else arc_rel

                anon_filename = anonymize_filename(filename, participant_mapping) if (anonymize and participant_mapping) else filename
                if anon_filename != filename:
                    stats["files_anonymized"] += 1

                # Progress (10–85% range)
                done = stats["files_processed"]
                pct = 10 + int(75 * done / total_files)
                if done % 20 == 0:
                    size_str = _fmt_size(output_zip)
                    size_part = f" — {size_str}" if size_str else ""
                    _report(min(pct, 84), f"Exporting files... ({done} of {total_files}){size_part}")

                # Write to ZIP (no staging copy for binary files)
                if filename.endswith(".json"):
                    zipf.writestr(arcname, _json_bytes(source_file))
                    if participant_mapping or mask_questions:
                        stats["files_anonymized"] += 1
                elif filename.endswith(".tsv") and anonymize and participant_mapping:
                    zipf.writestr(arcname, _tsv_bytes(source_file))
                    stats["files_anonymized"] += 1
                else:
                    zipf.write(source_file, arcname)

    _report(15, "Building ZIP archive...")
    _check_cancelled()

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:

        # Optional folders (derivatives, code, analysis)
        for folder_name, should_include in folders_to_copy.items():
            if not should_include:
                continue
            source_folder = project_path / folder_name
            if not source_folder.exists():
                continue
            _report(15, f"Adding {folder_name}/...")
            _check_cancelled()
            _add_tree(zipf, source_folder, folder_name)

        # BIDS subject folders
        for item in sorted(project_path.iterdir()):
            if not (item.is_dir() and item.name.startswith("sub-")):
                continue
            arc_name = (
                anonymize_filename(item.name, participant_mapping)
                if (anonymize and participant_mapping)
                else item.name
            )
            if arc_name != item.name:
                stats["files_anonymized"] += 1
            _check_cancelled()
            _add_tree(
                zipf, item, arc_name,
                skip_sessions=exclude_sessions or None,
                skip_modalities=exclude_modalities or None,
                skip_acq=exclude_acq or None,
            )

        _report(88, "Adding root files...")
        _check_cancelled()

        # Root-level files: include all files so PRISM metadata/config is complete
        # (e.g., dataset_description.json, .prismrc.json, task-*_survey.json).
        for source_file in sorted(project_path.iterdir()):
            if not source_file.is_file():
                continue
            if source_file.name == "participants_mapping.json":
                continue
            # Avoid embedding the output archive when user writes into project root.
            if source_file.resolve() == output_zip.resolve():
                continue
            filename = source_file.name
            if filename.endswith(".json"):
                zipf.writestr(filename, _json_bytes(source_file))
            elif filename.endswith(".tsv") and anonymize and participant_mapping:
                zipf.writestr(filename, _tsv_bytes(source_file))
            else:
                zipf.write(source_file, filename)
            stats["files_processed"] += 1

    final_size = _fmt_size(output_zip)
    size_part = f" ({final_size})" if final_size else ""
    _report(100, f"Export complete{size_part}")
    print(f"✓ Export complete: {output_zip}")
    print(f"  Processed {stats['files_processed']} files")
    if anonymize:
        print(f"  Anonymized {stats['files_anonymized']} files/folders")
        print("  🔒 Mapping file is not included in ZIP export")

    return stats
