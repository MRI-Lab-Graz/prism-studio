"""
Project export functionality with anonymization support.

This module provides utilities for exporting entire PRISM projects
with optional anonymization of participant IDs and copyright-protected content.
"""

import os
import json
import zipfile
import gzip
import io
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Set

from src.project_export_helpers import (
    _extract_export_task_label,
    _matches_excluded_acq_label,
)
from src.survey_scale_inference import get_survey_item_map


VERSION_CONTROL_METADATA_DIRS = frozenset({".git", ".datalad"})
VERSION_CONTROL_METADATA_FILES = frozenset(
    {".gitattributes", ".gitignore", ".gitmodules", "CHANGES"}
)
MRI_SUFFIX_LABEL_MODALITIES = frozenset({"anat", "dwi", "fmap", "perf"})


def _resolve_export_subject_scope(
    rel_parts: tuple[str, ...], *, subject_name: str | None, is_dir: bool
) -> tuple[str | None, str | None, str | None]:
    """Resolve subject/session/modality scope for raw and nested export trees."""
    subject_label = None
    part_index = 0

    if subject_name:
        subject_label = subject_name
    else:
        subject_index = next(
            (index for index, part in enumerate(rel_parts) if str(part).startswith("sub-")),
            None,
        )
        if subject_index is None:
            return None, None, None
        subject_label = rel_parts[subject_index]
        part_index = subject_index + 1

    session_label = None
    if part_index < len(rel_parts) and rel_parts[part_index].startswith("ses-"):
        session_label = rel_parts[part_index]
        part_index += 1

    modality_limit = len(rel_parts) if is_dir else len(rel_parts) - 1
    if part_index >= modality_limit:
        return subject_label, session_label, None

    return subject_label, session_label, rel_parts[part_index]


def _is_version_control_metadata_path(path_parts: tuple[str, ...]) -> bool:
    """Return True when a relative export path points at VCS/DataLad metadata."""
    normalized_parts = tuple(str(part) for part in path_parts if str(part))
    if not normalized_parts:
        return False

    if any(part in VERSION_CONTROL_METADATA_DIRS for part in normalized_parts):
        return True

    return normalized_parts[-1] in VERSION_CONTROL_METADATA_FILES


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
    from src.anonymizer import replace_participant_ids_in_text

    return replace_participant_ids_in_text(filename, mapping)


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
    include_sourcedata: bool = False,
    include_code: bool = True,
    include_analysis: bool = False,
    exclude_subjects: Optional[Set[str]] = None,
    exclude_sessions: Optional[Set[str]] = None,
    exclude_modalities: Optional[Set[str]] = None,
    exclude_acq: Optional[Dict[str, Set[str]]] = None,
    exclude_tasks: Optional[Dict[str, Set[str]]] = None,
    exclude_version_control_metadata: bool = False,
    scrub_mri_json: bool = False,
    scrub_mri_json_groups: Optional[Set[str]] = None,
    deface_anatomical_scans: bool = False,
    defacing_selected_variants: Optional[Set[str]] = None,
    clean_nifti_gzip_headers: bool = False,
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
        include_sourcedata: Include sourcedata/ folder
        include_code: Include code/ folder
        include_analysis: Include analysis/ folder
        exclude_subjects: Exclude selected subject directories (for example, {"sub-002"})
        exclude_version_control_metadata: Strip Git/DataLad metadata from ZIP
        deface_anatomical_scans: Deface selected anatomical scans in an export-only copy
            before writing them into the ZIP archive.
        defacing_selected_variants: Optional anatomical variant filter for export-only
            defacing.
        clean_nifti_gzip_headers: Normalize .nii.gz GZIP headers (mtime/FNAME)
            in exported copies for privacy-safe sharing.
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
    _saved_mapping_file: Optional[Path] = None
    if anonymize:
        participant_ids = collect_participant_ids(project_path)
        if participant_ids:
            # Save mapping to project's code/ directory (protected — not in ZIP).
            # create_participant_mapping() creates the parent directory automatically.
            _saved_mapping_file = project_path / "code" / "anonymization_map.json"
            participant_mapping = create_participant_mapping(
                list(participant_ids),
                _saved_mapping_file,
                id_length=id_length,
                deterministic=deterministic,
            )
            print(
                f"✓ Created anonymization mapping for {len(participant_mapping)} participants"
            )
            print(f"  Mapping saved to: {_saved_mapping_file}")
            print("  ⚠️  KEEP THIS FILE SECURE! It allows re-identification.")

    _report(10, "Scanning files...")
    _check_cancelled()

    # Decide which top-level folders to include
    folders_to_copy = {
        "derivatives": include_derivatives,
        "sourcedata": include_sourcedata,
        "code": include_code,
        "analysis": include_analysis,
    }

    normalized_exclude_subjects = {
        str(label).strip()
        for label in (exclude_subjects or set())
        if str(label).strip()
    }

    export_tree_root = project_path
    defacing_overlay_root: Optional[Path] = None
    defacing_workspace_root: Optional[Path] = None
    defacing_result: Optional[Dict[str, Any]] = None

    if deface_anatomical_scans:
        from src.datalad_execution import is_datalad_dataset
        from src.mri_json_scrubber import (
            deface_anatomical_scans as run_export_defacing,
            prepare_defacing_export_copy,
        )

        _report(12, "Preparing export-only MRI defacing...")
        _check_cancelled()

        defacing_workspace_root = Path(
            tempfile.mkdtemp(prefix="prism_export_defacing_")
        )
        use_full_export_copy = not exclude_version_control_metadata

        if use_full_export_copy and is_datalad_dataset(project_path):
            copy_summary = prepare_defacing_export_copy(
                project_path,
                defacing_workspace_root,
                selected_variants=defacing_selected_variants,
                excluded_subjects=exclude_subjects,
                excluded_sessions=exclude_sessions,
                preserve_datalad_metadata=True,
            )
            if not copy_summary.get("success"):
                raise RuntimeError(
                    str(
                        copy_summary.get("error")
                        or "Could not prepare DataLad-preserving export defacing copy."
                    )
                )
            export_tree_root = Path(
                str(copy_summary.get("target_path") or "")
            ).resolve(strict=False)
        elif use_full_export_copy:
            export_tree_root = defacing_workspace_root / project_path.name
            shutil.copytree(project_path, export_tree_root, symlinks=False)
        else:
            copy_summary = prepare_defacing_export_copy(
                project_path,
                defacing_workspace_root,
                selected_variants=defacing_selected_variants,
                excluded_subjects=exclude_subjects,
                excluded_sessions=exclude_sessions,
                preserve_datalad_metadata=False,
            )
            if not copy_summary.get("success"):
                raise RuntimeError(
                    str(
                        copy_summary.get("error")
                        or "Could not prepare export defacing overlay."
                    )
                )
            defacing_overlay_root = Path(
                str(copy_summary.get("target_path") or "")
            ).resolve(strict=False)

        defacing_target_root = export_tree_root if use_full_export_copy else defacing_overlay_root
        if defacing_target_root is None:
            raise RuntimeError("Export defacing target could not be prepared.")

        defacing_result = run_export_defacing(
            defacing_target_root,
            selected_variants=defacing_selected_variants,
            excluded_subjects=exclude_subjects,
            excluded_sessions=exclude_sessions,
        )
        if not defacing_result.get("success"):
            raise RuntimeError(
                str(
                    defacing_result.get("error")
                    or defacing_result.get("message")
                    or "Export-only MRI defacing failed."
                )
            )

    def _count_exportable_files(source_root: Path) -> int:
        total = 0
        for root, dirs, files in os.walk(source_root):
            rel_parts = Path(root).relative_to(source_root).parts
            if exclude_version_control_metadata:
                dirs[:] = [
                    dirname
                    for dirname in dirs
                    if not _is_version_control_metadata_path(rel_parts + (dirname,))
                ]
                files = [
                    filename
                    for filename in files
                    if not _is_version_control_metadata_path(rel_parts + (filename,))
                ]
            total += len(files)
        return total

    # Pre-count total files for accurate progress
    total_files = sum(
        _count_exportable_files(export_tree_root / folder_name)
        for folder_name, should_include in folders_to_copy.items()
        if should_include and (export_tree_root / folder_name).exists()
    )
    total_files += sum(
        _count_exportable_files(item)
        for item in export_tree_root.iterdir()
        if (
            item.is_dir()
            and item.name.startswith("sub-")
            and item.name not in normalized_exclude_subjects
        )
    )
    total_files = max(total_files, 1)

    stats: Dict[str, Any] = {
        "files_processed": 0,
        "files_anonymized": 0,
        "files_skipped_unfetched": 0,
        "unfetched_files": [],
        "participant_count": len(participant_mapping),
        "mapping_file": str(_saved_mapping_file) if _saved_mapping_file else None,
    }
    if defacing_result is not None:
        stats["defacing"] = defacing_result

    def _resolve_export_source_file(source_file: Path) -> Path:
        if defacing_overlay_root is None:
            return source_file

        try:
            rel_path = source_file.relative_to(project_path)
        except ValueError:
            return source_file

        overlay_candidate = defacing_overlay_root / rel_path
        return overlay_candidate if overlay_candidate.exists() else source_file

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
            from src.mri_json_scrubber import (
                is_mri_json_sidecar,
                detect_modality_from_path,
                scrub_sensitive_json_fields,
            )

            if is_mri_json_sidecar(source_file):
                modality = detect_modality_from_path(source_file)
                data, _removed = scrub_sensitive_json_fields(
                    data,
                    modality=modality,
                    selected_groups=scrub_mri_json_groups,
                )
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

    def _clean_nifti_gzip_bytes(source_file: Path) -> bytes:
        """Return .nii.gz payload with scrubbed GZIP header metadata.

        Sets mtime to 0 and removes embedded original filename (FNAME).
        If recompression fails, fall back to original file bytes.
        """
        try:
            with gzip.open(source_file, "rb") as gz_in:
                payload = gz_in.read()

            out_buffer = io.BytesIO()
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=out_buffer,
                mtime=0,
            ) as gz_out:
                gz_out.write(payload)
            return out_buffer.getvalue()
        except Exception:
            return source_file.read_bytes()

    def _add_tree(
        zipf: zipfile.ZipFile,
        source_root: Path,
        arc_prefix: str,
        skip_subjects: Optional[Set[str]] = None,
        skip_sessions: Optional[Set[str]] = None,
        skip_modalities: Optional[Set[str]] = None,
        skip_acq: Optional[Dict[str, Set[str]]] = None,
        skip_tasks: Optional[Dict[str, Set[str]]] = None,
        subject_name: Optional[str] = None,
    ) -> None:
        """Walk source_root and write every file directly into zipf."""
        for root, _dirs, files in os.walk(source_root):
            _check_cancelled()
            rel_root = Path(root).relative_to(source_root)
            # Check if this path is under an excluded session or modality
            rel_parts = rel_root.parts
            current_subject, current_session, current_modality = _resolve_export_subject_scope(
                rel_parts,
                subject_name=subject_name,
                is_dir=True,
            )
            if exclude_version_control_metadata:
                _dirs[:] = [
                    dirname
                    for dirname in _dirs
                    if not _is_version_control_metadata_path(rel_parts + (dirname,))
                ]
                files = [
                    filename
                    for filename in files
                    if not _is_version_control_metadata_path(rel_parts + (filename,))
                ]
            if skip_subjects and current_subject and current_subject in skip_subjects:
                _dirs[:] = []
                continue
            if skip_sessions and current_session and current_session in skip_sessions:
                _dirs[:] = []  # prune subtree
                continue
            if skip_modalities and current_modality and current_modality in skip_modalities:
                _dirs[:] = []
                continue
            for filename in files:
                # Keep participants mapping and anonymization map out of share ZIPs.
                if filename in ("participants_mapping.json", "anonymization_map.json"):
                    continue
                _file_subject, _file_session, _cur_modality = _resolve_export_subject_scope(
                    rel_parts + (filename,),
                    subject_name=subject_name,
                    is_dir=False,
                )
                if skip_subjects and _file_subject and _file_subject in skip_subjects:
                    continue
                if skip_sessions and _file_session and _file_session in skip_sessions:
                    continue
                if skip_modalities and _cur_modality and _cur_modality in skip_modalities:
                    continue
                # Filter by acq- label if requested
                if skip_acq and _cur_modality and _cur_modality in skip_acq:
                    if _matches_excluded_acq_label(filename, skip_acq[_cur_modality]):
                        continue
                if skip_tasks and _cur_modality and _cur_modality in skip_tasks:
                    task_label = _extract_export_task_label(filename, _cur_modality)
                    if task_label and task_label in skip_tasks[_cur_modality]:
                        continue
                source_file = Path(root) / filename
                resolved_source_file = _resolve_export_source_file(source_file)

                # DataLad-tracked projects can have git-annex symlinks whose
                # content was never `datalad get`-fetched locally (a broken
                # symlink). os.stat()/zipf.write() raise an unhandled,
                # uninformative FileNotFoundError on these — skip with a
                # clear record instead of crashing the whole export.
                if not resolved_source_file.exists():
                    stats["files_skipped_unfetched"] += 1
                    if len(stats["unfetched_files"]) < 50:
                        stats["unfetched_files"].append(
                            str((Path(rel_root) / filename).as_posix())
                        )
                    continue

                stats["files_processed"] += 1

                # Build archive path with optional anonymisation
                parts = list(rel_parts) + [filename]
                arc_rel = _anon_arc_path(parts)
                arcname = f"{arc_prefix}/{arc_rel}" if arc_prefix else arc_rel

                anon_filename = (
                    anonymize_filename(filename, participant_mapping)
                    if (anonymize and participant_mapping)
                    else filename
                )
                if anon_filename != filename:
                    stats["files_anonymized"] += 1

                # Progress (10–85% range)
                done = stats["files_processed"]
                pct = 10 + int(75 * done / total_files)
                if done % 20 == 0:
                    size_str = _fmt_size(output_zip)
                    size_part = f" — {size_str}" if size_str else ""
                    _report(
                        min(pct, 84),
                        f"Exporting files... ({done} of {total_files}){size_part}",
                    )

                # Write to ZIP (no staging copy for binary files)
                if filename.endswith(".json"):
                    zipf.writestr(arcname, _json_bytes(resolved_source_file))
                    if participant_mapping or mask_questions:
                        stats["files_anonymized"] += 1
                elif filename.endswith(".tsv") and anonymize and participant_mapping:
                    zipf.writestr(arcname, _tsv_bytes(resolved_source_file))
                    stats["files_anonymized"] += 1
                elif (
                    filename.lower().endswith(".nii.gz")
                    and clean_nifti_gzip_headers
                ):
                    zipf.writestr(
                        arcname, _clean_nifti_gzip_bytes(resolved_source_file)
                    )
                    stats["files_anonymized"] += 1
                else:
                    zipf.write(resolved_source_file, arcname)

    try:
        _report(15, "Building ZIP archive...")
        _check_cancelled()

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:

            # Optional folders (derivatives, code, analysis)
            for folder_name, should_include in folders_to_copy.items():
                if not should_include:
                    continue
                source_folder = export_tree_root / folder_name
                if not source_folder.exists():
                    continue
                _report(15, f"Adding {folder_name}/...")
                _check_cancelled()
                _add_tree(
                    zipf,
                    source_folder,
                    folder_name,
                    skip_subjects=normalized_exclude_subjects or None,
                    skip_sessions=exclude_sessions or None,
                    skip_modalities=exclude_modalities or None,
                    skip_acq=exclude_acq or None,
                    skip_tasks=exclude_tasks or None,
                )

            # BIDS subject folders
            for item in sorted(export_tree_root.iterdir()):
                if not (item.is_dir() and item.name.startswith("sub-")):
                    continue
                if item.name in normalized_exclude_subjects:
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
                    zipf,
                    item,
                    arc_name,
                    skip_subjects=normalized_exclude_subjects or None,
                    skip_sessions=exclude_sessions or None,
                    skip_modalities=exclude_modalities or None,
                    skip_acq=exclude_acq or None,
                    skip_tasks=exclude_tasks or None,
                    subject_name=item.name,
                )

            _report(88, "Adding root files...")
            _check_cancelled()

            # Root-level files: include all files so PRISM metadata/config is complete
            # (e.g., dataset_description.json, .prismrc.json, task-*_survey.json).
            for source_file in sorted(export_tree_root.iterdir()):
                if not source_file.is_file():
                    continue
                if exclude_version_control_metadata and _is_version_control_metadata_path(
                    (source_file.name,)
                ):
                    continue
                if source_file.name == "participants_mapping.json":
                    continue
                # Avoid embedding the output archive when user writes into project root.
                if source_file.resolve() == output_zip.resolve():
                    continue
                filename = source_file.name
                if exclude_tasks and "survey" in exclude_tasks:
                    task_label = _extract_export_task_label(filename, "survey")
                    if task_label and task_label in exclude_tasks["survey"]:
                        continue
                if filename.endswith(".json"):
                    zipf.writestr(filename, _json_bytes(source_file))
                elif filename.endswith(".tsv") and anonymize and participant_mapping:
                    zipf.writestr(filename, _tsv_bytes(source_file))
                elif filename.lower().endswith(".nii.gz") and clean_nifti_gzip_headers:
                    zipf.writestr(filename, _clean_nifti_gzip_bytes(source_file))
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
            if stats["mapping_file"]:
                print(f"  🔒 Mapping saved to: {stats['mapping_file']} (not in ZIP)")
            else:
                print("  🔒 No participants found; no mapping file written")

        return stats
    finally:
        if defacing_workspace_root is not None:
            shutil.rmtree(defacing_workspace_root, ignore_errors=True)
