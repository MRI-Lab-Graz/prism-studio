"""
Physio conversion logic for the Prism Web UI.
Extracted from conversion.py to reduce module size.
"""

from pathlib import Path
import io
import re
import shutil

from src.cross_platform import remove_tree
import tempfile
import zipfile
import base64
import threading
import uuid
from contextlib import nullcontext
from typing import Any
from flask import request, jsonify, session, send_file
from werkzeug.utils import secure_filename

# Shared utilities
from .conversion_job_store import ConversionJobStore
from .conversion_utils import (
    upload_basename,
    require_existing_project_root,
    resolve_existing_project_root,
    summarize_project_output_paths,
)
from src.conversion_to_project import ConversionCancelled, save_physio_batch_to_project, save_renamed_to_project
from src.physio_varioport import run_varioport_conversion
from src.physio_renamer import (
    rename_one,
    normalize_project_dest_root as _normalize_project_dest_root,
    normalize_subject_rewrite_mode as _normalize_subject_rewrite_mode,
    resolve_project_copy_root as _resolve_project_copy_root,
)

# Optional dependencies
convert_varioport: Any = None
try:
    from helpers.physio.convert_varioport import convert_varioport as _convert_varioport

    convert_varioport = _convert_varioport
except ImportError:
    pass


_batch_job_store = ConversionJobStore(log_level_key="level")
_batch_jobs_lock = _batch_job_store.lock
_batch_jobs = _batch_job_store.jobs


def _requested_project_path() -> str | None:
    raw_value = (
        request.form.get("project_path") or request.args.get("project_path") or ""
    ).strip()
    return raw_value or None


def _append_job_log(job_id: str, message: str, level: str = "info"):
    _batch_job_store.append_log(job_id, message, level)


def _is_job_cancelled(job_id: str) -> bool:
    """Check if job has been marked for cancellation."""
    return _batch_job_store.is_cancelled(job_id)


def _mark_job_cancelled(job_id: str) -> bool:
    """Mark job as cancelled. Returns True if job existed."""
    return _batch_job_store.cancel(job_id)


def _run_batch_job(job_id: str, config: dict[str, Any]):
    def log_callback(message: str, level: str = "info"):
        _append_job_log(job_id, message, level)

    tmp_dir = config["tmp_dir"]
    try:
        source_dir = config["source_dir"]
        # Check if cancellation was requested before we start
        if _is_job_cancelled(job_id):
            _append_job_log(
                job_id, "⏹️ Batch conversion cancelled (before start)", "warning"
            )
            _batch_job_store.failure(job_id, "Cancelled by user", status="cancelled")
            return

        output_dir = Path(tmp_dir) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        write_direct_to_project = False

        if not config["dry_run"] and config["save_to_project"]:
            p_path = config.get("project_path")
            if p_path:
                project_root = Path(p_path)
                if project_root.exists():
                    log_callback(
                        f"📦 Staging converted files in temporary output before copying to project: {project_root}",
                        "info",
                    )
                else:
                    log_callback(
                        f"⚠️ Project path not found: {p_path}. Falling back to temporary output.",
                        "warning",
                    )
            else:
                log_callback(
                    "⚠️ No active project selected; writing to temporary output only.",
                    "warning",
                )

        result = batch_convert_folder(
            source_dir,
            output_dir,
            physio_sampling_rate=config["sampling_rate"],
            generate_physio_reports=config["generate_physio_reports"],
            modality_filter=config["modality_filter"],
            log_callback=log_callback,
            cancel_check=lambda: _is_job_cancelled(job_id),
            dry_run=config["dry_run"],
            physio_destination=config["physio_destination"],
        )

        if _is_job_cancelled(job_id):
            _append_job_log(
                job_id, "⏹️ Batch conversion cancelled (mid-process)", "warning"
            )
            _batch_job_store.failure(job_id, "Cancelled by user", status="cancelled")
            return

        payload: dict[str, Any] = {
            "converted": result.success_count,
            "errors": result.error_count,
            "new_files": result.new_files,
            "existing_files": result.existing_files,
            "dry_run": config["dry_run"],
            "warnings": [],
            "project_saved": False,
            "project_output_root": None,
            "project_output_paths": [],
            "project_output_path": None,
            "project_output_count": 0,
        }

        conflicts = None if config["dry_run"] else describe_conflicts(result, output_dir)
        if conflicts:
            _batch_job_store.failure(job_id, conflicts[0])
            return

        if not config["dry_run"]:
            create_dataset_description(output_dir, name=config["dataset_name"])

            if config["save_to_project"] and not write_direct_to_project:
                p_path = config["project_path"]
                if p_path:
                    base_project_root = Path(p_path)
                    if base_project_root.exists():
                        try:
                            project_save = save_physio_batch_to_project(
                                project_root=base_project_root,
                                staged_root=output_dir,
                                converted=result.converted,
                                dataset_name=config["dataset_name"],
                                dest_root=config["dest_root"],
                                flat_structure=bool(config.get("flat_structure", False)),
                                modality_filter=config["modality_filter"],
                                subject_rewrite_mode=config.get("subject_rewrite_mode", "keep"),
                                cancel_check=lambda: _is_job_cancelled(job_id),
                                log_fn=log_callback,
                            )
                        except ConversionCancelled:
                            _append_job_log(
                                job_id,
                                "⏹️ Batch conversion cancelled while copying staged files into the project",
                                "warning",
                            )
                            _batch_job_store.failure(job_id, "Cancelled by user", status="cancelled")
                            return
                        copied_files = project_save.output_paths
                        payload["datalad"] = project_save.datalad
                        payload["warnings"].extend(project_save.warnings)

                        if copied_files:
                            output_paths = summarize_project_output_paths(
                                copied_files,
                                project_root=base_project_root,
                                limit=50,
                            )
                            payload["project_saved"] = True
                            payload["project_output_root"] = str(base_project_root)
                            payload["project_output_paths"] = output_paths
                            payload["project_output_path"] = (
                                output_paths[0] if output_paths else None
                            )
                            payload["project_output_count"] = len(copied_files)

                    else:
                        payload["warnings"].append(
                            f"Project path not found: {p_path}. Copy to project skipped."
                        )
                else:
                    payload["warnings"].append(
                        "No active project selected; copy to project skipped."
                    )

        _batch_job_store.success(job_id, payload)
    except Exception as e:
        _batch_job_store.failure(job_id, str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def api_batch_convert_start():
    """Start batch conversion asynchronously and return a job id for polling."""
    if not batch_convert_folder:
        return jsonify({"error": "Batch conversion not available"}), 500

    dataset_name = (request.form.get("dataset_name") or "Converted Dataset").strip()
    modality_filter = request.form.get("modality", "all")
    save_to_project = (request.form.get("save_to_project") or "false").lower() == "true"
    dest_root = _normalize_project_dest_root(request.form.get("dest_root") or "root")
    flat_structure = (request.form.get("flat_structure") or "false").lower() == "true"
    subject_rewrite_mode = _normalize_subject_rewrite_mode(
        request.form.get("subject_rewrite_mode") or "keep"
    )
    sampling_rate_str = request.form.get("sampling_rate", "").strip()
    generate_physio_reports = (
        request.form.get("generate_physio_reports") or "false"
    ).lower() == "true"
    dry_run = (request.form.get("dry_run") or "false").lower() == "true"
    folder_path = request.form.get("folder_path", "").strip()
    physio_destination = request.form.get("physio_destination") or None

    try:
        sampling_rate = float(sampling_rate_str) if sampling_rate_str else None
    except ValueError:
        return jsonify({"error": "sampling_rate must be a number"}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_batch_convert_job_")
    tmp_path = Path(tmp_dir)
    input_dir = tmp_path / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    if folder_path:
        folder_path_obj = Path(folder_path)
        if not folder_path_obj.exists() or not folder_path_obj.is_dir():
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return jsonify({"error": f"Folder not found: {folder_path}"}), 400
        source_dir = folder_path_obj
    else:
        files = request.files.getlist("files[]") or request.files.getlist("files")
        if not files:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return (
                jsonify({"error": "No files uploaded and no folder path provided"}),
                400,
            )

        valid_extensions = {
            ".raw",
            ".vpd",
            ".edf",
            ".tsv",
            ".tsv.gz",
            ".csv",
            ".txt",
            ".json",
            ".nii",
            ".nii.gz",
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
        }

        valid_count = 0
        invalid_pattern_files = []
        unsupported_extension_files = []
        for f in files:
            if not f or not f.filename:
                continue
            filename = secure_filename(upload_basename(f.filename))
            lower_name = filename.lower()
            if lower_name.endswith(".nii.gz"):
                ext = ".nii.gz"
            elif lower_name.endswith(".tsv.gz"):
                ext = ".tsv.gz"
            else:
                ext = Path(filename).suffix.lower()

            if ext in valid_extensions:
                if parse_bids_filename(filename):
                    f.save(str(input_dir / filename))
                    valid_count += 1
                else:
                    invalid_pattern_files.append(filename)
            else:
                unsupported_extension_files.append(filename)

        if valid_count == 0:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            hints = []
            if invalid_pattern_files:
                preview = ", ".join(invalid_pattern_files[:3])
                if len(invalid_pattern_files) > 3:
                    preview += ", ..."
                hints.append(
                    "Invalid filename pattern for: "
                    f"{preview}. Expected: sub-<id>_[ses-<id>_]task-<id>.<ext> "
                    "(example: sub-003_ses-1_task-rest.vpd)."
                )
            if unsupported_extension_files:
                preview = ", ".join(unsupported_extension_files[:3])
                if len(unsupported_extension_files) > 3:
                    preview += ", ..."
                hints.append(f"Unsupported extension for: {preview}.")

            details = " ".join(hints) if hints else "No valid files to convert."
            return jsonify({"error": details}), 400
        source_dir = input_dir

    project_path = _requested_project_path() or session.get("current_project_path")
    if save_to_project and not dry_run:
        try:
            project_root = require_existing_project_root(
                project_path,
                missing_message="No active project selected. Open a project before saving converted files.",
                missing_path_message="The selected project path no longer exists. Reopen the project and retry the conversion.",
            )
        except (ValueError, FileNotFoundError) as error:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return jsonify({"error": str(error)}), 400
        project_path = str(project_root)

    try:
        check_physio_destination(source_dir, modality_filter, physio_destination)
    except PhysioDestinationError as error:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": str(error)}), 400

    job_id = ""
    for _ in range(5):
        candidate = uuid.uuid4().hex
        try:
            _batch_job_store.create(candidate)
            job_id = candidate
            break
        except ValueError:
            continue
    if not job_id:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({"error": "Could not allocate conversion job id"}), 500

    _append_job_log(job_id, "🚀 Batch conversion job started", "info")

    config = {
        "tmp_dir": tmp_dir,
        "source_dir": source_dir,
        "sampling_rate": sampling_rate,
        "generate_physio_reports": generate_physio_reports,
        "modality_filter": modality_filter,
        "dry_run": dry_run,
        "physio_destination": physio_destination,
        "dataset_name": dataset_name,
        "save_to_project": save_to_project,
        "dest_root": dest_root,
        "flat_structure": flat_structure,
        "subject_rewrite_mode": subject_rewrite_mode,
        "project_path": project_path,
    }

    thread = threading.Thread(target=_run_batch_job, args=(job_id, config), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id}), 200


def api_batch_convert_status(job_id: str):
    """Get incremental status and logs for an async batch conversion job."""
    try:
        cursor = int(request.args.get("cursor", "0"))
    except ValueError:
        cursor = 0

    payload = _batch_job_store.snapshot(job_id, cursor)
    if payload is None:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(payload), 200


def api_batch_convert_cancel(job_id: str):
    """Cancel an async batch conversion job."""
    if _mark_job_cancelled(job_id):
        _append_job_log(job_id, "⏹️ User requested cancellation", "warning")
        return (
            jsonify(
                {
                    "message": "Cancellation requested for job",
                    "job_id": job_id,
                    "status": "cancelling",
                }
            ),
            200,
        )
    return jsonify({"error": "Job not found or already finished"}), 404


def api_batch_convert_metrics():
    """Return in-memory batch conversion job metrics for debugging/monitoring."""
    return jsonify(_batch_job_store.metrics()), 200


batch_convert_folder: Any = None
check_physio_destination: Any = None
create_dataset_description: Any = None
describe_conflicts: Any = None
parse_bids_filename: Any = None


PhysioDestinationError: Any = type("PhysioDestinationError", (ValueError,), {})  # placeholder if src.batch_convert is missing


try:
    from src import batch_convert as _batch_convert

    PhysioDestinationError = _batch_convert.PhysioDestinationError
    batch_convert_folder = _batch_convert.batch_convert_folder
    check_physio_destination = _batch_convert.check_physio_destination
    create_dataset_description = _batch_convert.create_dataset_description
    describe_conflicts = _batch_convert.describe_conflicts
    parse_bids_filename = _batch_convert.parse_bids_filename
except (ImportError, AttributeError):
    pass


def check_sourcedata_physio():
    """Check if sourcedata/physio folder exists in current project."""
    try:
        project_root = resolve_existing_project_root(
            _requested_project_path() or session.get("current_project_path")
        )
        if project_root is None:
            return jsonify({"exists": False, "message": "No project selected"}), 400

        sourcedata_physio = project_root / "sourcedata" / "physio"

        exists = sourcedata_physio.exists() and sourcedata_physio.is_dir()

        if exists:
            # Count .raw and .vpd files (case-insensitive)
            all_files = list(sourcedata_physio.iterdir())
            physio_files = [
                f for f in all_files if f.suffix.lower() in [".raw", ".vpd"]
            ]
            file_count = len(physio_files)
        else:
            file_count = 0

        return (
            jsonify(
                {
                    "exists": exists,
                    "path": sourcedata_physio.as_posix() if exists else None,
                    "message": (
                        f"Found sourcedata/physio folder with {file_count} files"
                        if exists
                        else "sourcedata/physio folder not found"
                    ),
                }
            ),
            200,
        )
    except Exception as exc:
        return jsonify({"exists": False, "message": str(exc)}), 500


def api_physio_convert():
    """Convert an uploaded Varioport file (.raw/.vpd) into EDF+ (.edf) + sidecar (.json) and return as ZIP."""
    if convert_varioport is None:
        return jsonify({"error": "Physio conversion (Varioport) not available"}), 500

    uploaded_file = request.files.get("raw") or request.files.get("file")
    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".raw", ".vpd"}:
        return (
            jsonify({"error": "Only Varioport .raw and .vpd files are supported"}),
            400,
        )

    task = (request.form.get("task") or "").strip()
    base_freq = (request.form.get("sampling_rate") or "").strip() or None
    try:
        base_freq_val = float(base_freq) if base_freq is not None else None
    except Exception:
        return jsonify({"error": "sampling_rate must be a number"}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_physio_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        out_edf = tmp_dir_path / (input_path.stem + ".edf")
        out_json = tmp_dir_path / (input_path.stem + ".json")

        run_varioport_conversion(
            convert_varioport, input_path, out_edf, out_json, task=task, sampling_rate=base_freq_val, log_fn=lambda _message: None
        )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            if out_edf.exists():
                zf.write(out_edf, out_edf.name)
            if out_json.exists():
                zf.write(out_json, out_json.name)
        mem.seek(0)

        return send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="varioport_edfplus.zip",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def api_batch_convert():
    """Batch convert physio files from a flat folder structure."""
    if not batch_convert_folder:
        return jsonify({"error": "Batch conversion not available"}), 500

    logs = []

    def log_callback(message: str, level: str = "info"):
        # Just store the plain message + level
        # Colors will be applied on the frontend based on the level
        logs.append({"message": message, "level": level})

    dataset_name = (request.form.get("dataset_name") or "Converted Dataset").strip()
    modality_filter = request.form.get("modality", "all")
    save_to_project = (request.form.get("save_to_project") or "false").lower() == "true"
    dest_root = _normalize_project_dest_root(request.form.get("dest_root") or "root")
    flat_structure = (request.form.get("flat_structure") or "false").lower() == "true"
    subject_rewrite_mode = _normalize_subject_rewrite_mode(
        request.form.get("subject_rewrite_mode") or "keep"
    )
    sampling_rate_str = request.form.get("sampling_rate", "").strip()
    generate_physio_reports = (
        request.form.get("generate_physio_reports") or "false"
    ).lower() == "true"
    dry_run = (request.form.get("dry_run") or "false").lower() == "true"
    folder_path = request.form.get("folder_path", "").strip()
    physio_destination = request.form.get("physio_destination") or None
    server_file_paths = request.form.getlist("server_file_paths[]") or request.form.getlist(
        "server_file_paths"
    )

    try:
        sampling_rate = float(sampling_rate_str) if sampling_rate_str else None
    except ValueError:
        return jsonify({"error": "sampling_rate must be a number", "logs": logs}), 400

    current_project_root = None
    if save_to_project and not dry_run:
        try:
            current_project_root = require_existing_project_root(
                _requested_project_path() or session.get("current_project_path"),
                missing_message="No active project selected. Open a project before saving converted files.",
                missing_path_message="The selected project path no longer exists. Reopen the project and retry the conversion.",
            )
        except (ValueError, FileNotFoundError) as error:
            return jsonify({"error": str(error), "logs": logs}), 400

    files = request.files.getlist("files[]") or request.files.getlist("files")
    selected_server_files: list[Path] = []
    seen_server_paths: set[str] = set()
    for raw_server_path in server_file_paths:
        candidate_text = str(raw_server_path or "").strip()
        if not candidate_text:
            continue
        candidate = Path(candidate_text).expanduser().resolve()
        if not candidate.exists() or not candidate.is_file():
            return (
                jsonify(
                    {
                        "error": f"Server file not found: {candidate_text}",
                        "logs": logs,
                    }
                ),
                400,
            )
        candidate_key = str(candidate)
        if candidate_key in seen_server_paths:
            continue
        seen_server_paths.add(candidate_key)
        selected_server_files.append(candidate)

    # If folder_path is provided, use it directly instead of uploaded files
    if folder_path:
        folder_path_obj = Path(folder_path)
        if not folder_path_obj.exists() or not folder_path_obj.is_dir():
            return (
                jsonify({"error": f"Folder not found: {folder_path}", "logs": logs}),
                400,
            )

        log_callback(f"📂 Using folder: {folder_path}", "info")

        tmp_dir = tempfile.mkdtemp(prefix="prism_batch_convert_")
        try:
            tmp_path = Path(tmp_dir)
            output_dir = tmp_path / "output"
            output_dir.mkdir()

            # Call batch_convert directly with the source folder
            result = batch_convert_folder(
                folder_path_obj,
                output_dir,
                physio_sampling_rate=sampling_rate,
                generate_physio_reports=generate_physio_reports,
                modality_filter=modality_filter,
                log_callback=log_callback,
                dry_run=dry_run,
                physio_destination=physio_destination,
            )

            # If not a dry-run, move files to project if save_to_project is true
            copied_output_paths: list[Path] = []
            datalad_copy = None
            folder_warnings: list[str] = []
            conflicts = None if dry_run else describe_conflicts(result, output_dir)
            if conflicts:
                message, conflicts_info = conflicts
                return jsonify({"error": message, "conflicts": conflicts_info, "logs": logs}), 409
            if not dry_run:
                create_dataset_description(output_dir, name=dataset_name)  # as the async job does
            if not dry_run and save_to_project:
                project_save = save_physio_batch_to_project(
                    project_root=current_project_root,
                    staged_root=output_dir,
                    converted=result.converted,
                    dataset_name=dataset_name,
                    dest_root=dest_root,
                    flat_structure=flat_structure,
                    modality_filter=modality_filter,
                    subject_rewrite_mode=subject_rewrite_mode,
                    log_fn=log_callback,
                )
                folder_warnings = project_save.warnings
                datalad_copy = project_save.datalad
                copied_output_paths = project_save.output_paths

            output_paths = []
            if copied_output_paths and current_project_root is not None:
                output_paths = summarize_project_output_paths(
                    copied_output_paths,
                    project_root=current_project_root,
                    limit=50,
                )

            return jsonify(
                {
                    "converted": result.success_count,
                    "errors": result.error_count,
                    "new_files": result.new_files,
                    "existing_files": result.existing_files,
                    "logs": logs,
                    "dry_run": dry_run,
                    "project_saved": bool(copied_output_paths),
                    "project_output_root": (
                        str(current_project_root)
                        if copied_output_paths and current_project_root is not None
                        else None
                    ),
                    "project_output_paths": output_paths,
                    "project_output_path": output_paths[0] if output_paths else None,
                    "project_output_count": len(copied_output_paths),
                    "datalad": datalad_copy,
                    "warnings": folder_warnings,
                }
            )
        except PhysioDestinationError as error:
            return jsonify({"error": str(error), "logs": logs}), 400
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    if not files and not selected_server_files:
        return (
            jsonify(
                {
                    "error": "No files uploaded, no server files selected, and no folder path provided",
                    "logs": logs,
                }
            ),
            400,
        )

    # Accept a wider range of extensions for the batch organizer
    valid_extensions = {
        ".raw",
        ".vpd",
        ".edf",
        ".tsv",
        ".tsv.gz",
        ".csv",
        ".txt",
        ".json",
        ".nii",
        ".nii.gz",
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
    }
    validated_files = []
    for f in files:
        if not f or not f.filename:
            continue
        filename = secure_filename(upload_basename(f.filename))

        # Handle .nii.gz and .tsv.gz
        lower_name = filename.lower()
        if lower_name.endswith(".nii.gz"):
            ext = ".nii.gz"
        elif lower_name.endswith(".tsv.gz"):
            ext = ".tsv.gz"
        else:
            ext = Path(filename).suffix.lower()

        if ext in valid_extensions and parse_bids_filename(filename):
            validated_files.append((f, filename))

    validated_server_files: list[tuple[Path, str]] = []
    for server_file in selected_server_files:
        filename = secure_filename(server_file.name)
        if not filename:
            continue

        lower_name = filename.lower()
        if lower_name.endswith(".nii.gz"):
            ext = ".nii.gz"
        elif lower_name.endswith(".tsv.gz"):
            ext = ".tsv.gz"
        else:
            ext = Path(filename).suffix.lower()

        if ext in valid_extensions and parse_bids_filename(filename):
            validated_server_files.append((server_file, filename))

    if not validated_files and not validated_server_files:
        return jsonify({"error": "No valid files to convert.", "logs": logs}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_batch_convert_")
    warnings = []
    try:
        tmp_path = Path(tmp_dir)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        used_input_filenames: set[str] = set()

        for f, filename in validated_files:
            if filename in used_input_filenames:
                return (
                    jsonify(
                        {
                            "error": f"Duplicate filename selected: {filename}",
                            "logs": logs,
                        }
                    ),
                    400,
                )
            f.save(str(input_dir / filename))
            used_input_filenames.add(filename)

        for server_file, filename in validated_server_files:
            if filename in used_input_filenames:
                return (
                    jsonify(
                        {
                            "error": f"Duplicate filename selected: {filename}",
                            "logs": logs,
                        }
                    ),
                    400,
                )
            shutil.copy2(server_file, input_dir / filename)
            used_input_filenames.add(filename)

        if validated_server_files:
            log_callback(
                f"📄 Using {len(validated_server_files)} server-selected file(s)",
                "info",
            )

        result = batch_convert_folder(
            input_dir,
            output_dir,
            physio_sampling_rate=sampling_rate,
            generate_physio_reports=generate_physio_reports,
            modality_filter=modality_filter,
            log_callback=log_callback,
            dry_run=dry_run,
            physio_destination=physio_destination,
        )

        if dry_run:
            # For dry run, just return the logs (no file creation)
            return jsonify(
                {
                    "converted": result.success_count,
                    "errors": result.error_count,
                    "new_files": result.new_files,
                    "existing_files": result.existing_files,
                    "logs": logs,
                    "dry_run": True,
                }
            )

        create_dataset_description(output_dir, name=dataset_name)

        conflicts = describe_conflicts(result, output_dir)
        if conflicts:
            message, conflicts_info = conflicts
            return jsonify({"error": message, "conflicts": conflicts_info, "logs": logs}), 409

        project_saved = False
        base_project_root = None
        datalad_copy = None
        copied_output_paths: list[Path] = []
        if save_to_project:
            p_path = _requested_project_path() or session.get("current_project_path")
            if p_path:
                base_project_root = resolve_existing_project_root(p_path)
                if base_project_root is None:
                    warnings.append(f"Project path not found: {p_path}. Copy to project skipped.")
            else:
                warnings.append("No active project selected; copy to project skipped.")

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(output_dir))

        if base_project_root is not None:
            create_dataset_description(output_dir, name=dataset_name)  # as the async job does
            project_save = save_physio_batch_to_project(
                project_root=base_project_root,
                staged_root=output_dir,
                converted=result.converted,
                dataset_name=dataset_name,
                dest_root=dest_root,
                flat_structure=flat_structure,
                modality_filter=modality_filter,
                subject_rewrite_mode=subject_rewrite_mode,
                log_fn=log_callback,
            )
            warnings.extend(project_save.warnings)
            datalad_copy = project_save.datalad
            copied_output_paths = project_save.output_paths
            project_saved = bool(copied_output_paths)

        output_paths = []
        if copied_output_paths and base_project_root is not None:
            output_paths = summarize_project_output_paths(
                copied_output_paths,
                project_root=base_project_root,
                limit=50,
            )

        import base64

        zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        return jsonify(
            {
                "status": "success",
                "logs": logs,
                "zip": zip_base64,
                "converted": result.success_count,
                "errors": result.error_count,
                "project_saved": project_saved,
                "project_output_root": (
                    str(base_project_root)
                    if copied_output_paths and base_project_root is not None
                    else None
                ),
                "project_output_paths": output_paths,
                "project_output_path": output_paths[0] if output_paths else None,
                "project_output_count": len(copied_output_paths),
                "datalad": datalad_copy,
                "warnings": warnings,
            }
        )
    except PhysioDestinationError as e:
        return jsonify({"error": str(e), "logs": logs}), 400
    except Exception as e:
        return jsonify({"error": str(e), "logs": logs}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def api_physio_rename():
    """Rename uploaded files based on a regex pattern and return a ZIP."""
    pattern = request.form.get("pattern", "")
    replacement = request.form.get("replacement", "")
    dry_run = request.form.get("dry_run", "false").lower() == "true"
    organize = request.form.get("organize", "false").lower() == "true"
    modality = request.form.get("modality", "physio")
    save_to_project = request.form.get("save_to_project", "false").lower() == "true"
    skip_zip = request.form.get("skip_zip", "false").lower() == "true"
    dest_root = _normalize_project_dest_root(request.form.get("dest_root") or "root")
    flat_structure = (request.form.get("flat_structure") or "false").lower() == "true"
    id_source = (request.form.get("id_source") or "filename").strip().lower()
    if id_source not in {"filename", "folder"}:
        id_source = "filename"
    folder_subject_level_str = (request.form.get("folder_subject_level") or "2").strip()
    folder_session_level_str = (request.form.get("folder_session_level") or "1").strip()
    try:
        folder_subject_level = max(1, int(folder_subject_level_str))
    except ValueError:
        folder_subject_level = 2
    try:
        folder_session_level = max(1, int(folder_session_level_str))
    except ValueError:
        folder_session_level = 1
    folder_subject_value = (request.form.get("folder_subject_value") or "").strip()
    folder_session_value = (request.form.get("folder_session_value") or "").strip()
    folder_example_path = (request.form.get("folder_example_path") or "").strip()
    folder_path = (request.form.get("folder_path") or "").strip()
    server_file_paths = request.form.getlist("server_file_paths[]") or request.form.getlist(
        "server_file_paths"
    )
    subject_rewrite_mode = _normalize_subject_rewrite_mode(
        request.form.get("subject_rewrite_mode") or "keep"
    )

    files = request.files.getlist("files[]") or request.files.getlist("files")
    filenames = request.form.getlist("filenames[]") or request.form.getlist("filenames")
    source_paths = request.form.getlist("source_paths[]") or request.form.getlist(
        "source_paths"
    )

    server_files: list[tuple[Path, str]] = []
    seen_server_paths: set[str] = set()
    if folder_path:
        folder_root = Path(folder_path).expanduser().resolve()
        if not folder_root.exists() or not folder_root.is_dir():
            return jsonify({"error": f"Folder not found: {folder_path}"}), 400

        for candidate in sorted(folder_root.rglob("*")):
            if not candidate.is_file():
                continue
            if any(part.startswith(".") for part in candidate.parts):
                continue
            candidate_key = str(candidate)
            if candidate_key in seen_server_paths:
                continue
            seen_server_paths.add(candidate_key)
            server_files.append((candidate, candidate.relative_to(folder_root).as_posix()))

    for raw_server_path in server_file_paths:
        candidate_text = str(raw_server_path or "").strip()
        if not candidate_text:
            continue

        candidate = Path(candidate_text).expanduser().resolve()
        if not candidate.exists() or not candidate.is_file():
            return jsonify({"error": f"Server file not found: {candidate_text}"}), 400

        candidate_key = str(candidate)
        if candidate_key in seen_server_paths:
            continue
        seen_server_paths.add(candidate_key)
        server_files.append((candidate, candidate_text))

    if not files and not filenames and not server_files and not dry_run:
        return jsonify({"error": "No files or filenames provided"}), 400

    if save_to_project and flat_structure and dest_root == "prism":
        return (
            jsonify(
                {
                    "error": "Flat output cannot be copied into the PRISM root. Enable PRISM folders or copy to rawdata/sourcedata instead."
                }
            ),
            400,
        )

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return jsonify({"error": f"Invalid regex: {str(e)}"}), 400

    results = []
    warnings = []

    if dry_run:
        source_names = (
            filenames if filenames else [f.filename for f in files if f.filename]
        )
        if not source_names and server_files:
            source_names = [file_path.name for file_path, _ in server_files]
            source_paths = [relative_path for _, relative_path in server_files]

        for idx, fname in enumerate(source_names):
            source_path = source_paths[idx] if idx < len(source_paths) else fname
            try:
                new_name, zip_path = rename_one(
                    source_path,
                    pattern=regex,
                    replacement=replacement,
                    id_source=id_source,
                    folder_subject_level=folder_subject_level,
                    folder_session_level=folder_session_level,
                    folder_example_path=folder_example_path,
                    folder_subject_value=folder_subject_value,
                    folder_session_value=folder_session_value,
                    modality=modality,
                    organize=organize,
                    parse_bids_filename=parse_bids_filename,
                )

                results.append(
                    {
                        "old": source_path,
                        "new": new_name,
                        "path": zip_path,
                        "success": True,
                    }
                )
            except Exception as e:
                results.append({"old": source_path, "new": str(e), "success": False})
        return jsonify({"results": results, "warnings": warnings})

    if not files and not server_files:
        return jsonify({"error": "No files uploaded for renaming"}), 400

    mem = io.BytesIO() if not skip_zip else None
    project_root = None
    base_project_root = None
    copied_output_paths: list[Path] = []
    rename_items: list[tuple[Path, str]] = []
    copy_stage_dir: Path | None = None
    if save_to_project:
        try:
            base_project_root = require_existing_project_root(
                _requested_project_path() or session.get("current_project_path"),
                missing_message="No active project selected. Open a project before copying renamed files.",
                missing_path_message="The selected project path no longer exists. Reopen the project and retry the rename.",
            )
        except (ValueError, FileNotFoundError) as error:
            return jsonify({"error": str(error)}), 400

        project_root = _resolve_project_copy_root(base_project_root, dest_root)
        project_root.mkdir(parents=True, exist_ok=True)
        copy_stage_dir = Path(tempfile.mkdtemp(prefix="prism_physio_rename_copy_"))

    try:
        zip_context = (
            zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED)
            if not skip_zip
            else nullcontext(None)
        )
        with zip_context as zf:
            for idx, f in enumerate(files):
                if not f or not f.filename:
                    continue
                source_path = (
                    source_paths[idx] if idx < len(source_paths) else f.filename
                )

                try:
                    new_name, zip_path = rename_one(
                        source_path,
                        pattern=regex,
                        replacement=replacement,
                        id_source=id_source,
                        folder_subject_level=folder_subject_level,
                        folder_session_level=folder_session_level,
                        folder_example_path=folder_example_path,
                        folder_subject_value=folder_subject_value,
                        folder_session_value=folder_session_value,
                        modality=modality,
                        organize=organize,
                        parse_bids_filename=parse_bids_filename,
                    )
                    f_content = f.read()
                    if zf is not None:
                        zf.writestr(zip_path, f_content)

                    if project_root:
                        if copy_stage_dir is None:
                            raise ValueError("Copy staging folder is unavailable.")
                        staged_source = copy_stage_dir / f"upload_{idx:05d}_{new_name}"
                        staged_source.write_bytes(f_content)
                        rename_items.append((staged_source, new_name))

                    results.append(
                        {
                            "old": source_path,
                            "new": new_name,
                            "success": True,
                            "path": zip_path,
                        }
                    )
                except Exception as e:
                    results.append(
                        {"old": source_path, "new": str(e), "success": False}
                    )

            for server_file, server_source_path in server_files:
                try:
                    new_name, zip_path = rename_one(
                        server_source_path,
                        pattern=regex,
                        replacement=replacement,
                        id_source=id_source,
                        folder_subject_level=folder_subject_level,
                        folder_session_level=folder_session_level,
                        folder_example_path=folder_example_path,
                        folder_subject_value=folder_subject_value,
                        folder_session_value=folder_session_value,
                        modality=modality,
                        organize=organize,
                        parse_bids_filename=parse_bids_filename,
                    )
                    f_content = server_file.read_bytes()
                    if zf is not None:
                        zf.writestr(zip_path, f_content)

                    if project_root:
                        rename_items.append((server_file, new_name))

                    results.append(
                        {
                            "old": server_source_path,
                            "new": new_name,
                            "success": True,
                            "path": zip_path,
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "old": server_source_path,
                            "new": str(e),
                            "success": False,
                        }
                    )

        copy_result = None
        if rename_items and base_project_root is not None:
            project_save = save_renamed_to_project(
                project_root=base_project_root,
                items=rename_items,
                dest_root=dest_root,
                flat_structure=flat_structure,
                modality=modality,
                organize=organize,
                subject_rewrite_mode=subject_rewrite_mode,
                parse_bids_filename=parse_bids_filename,
            )
            warnings.extend(project_save.warnings)
            copy_result = project_save.datalad
            copied_output_paths = project_save.output_paths

        zip_base64 = None
        if not skip_zip and mem is not None:
            mem.seek(0)
            zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        output_paths = []
        if copied_output_paths and base_project_root is not None:
            output_paths = summarize_project_output_paths(
                copied_output_paths,
                project_root=base_project_root,
                limit=50,
            )

        return jsonify(
            {
                "status": "success",
                "results": results,
                "zip": zip_base64,
                "project_saved": bool(copied_output_paths),
                "project_output_root": (
                    str(base_project_root)
                    if copied_output_paths and base_project_root is not None
                    else None
                ),
                "project_output_paths": output_paths,
                "project_output_path": output_paths[0] if output_paths else None,
                "project_output_count": len(copied_output_paths),
                "datalad": copy_result,
                "warnings": warnings,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if copy_stage_dir is not None:
            remove_tree(copy_stage_dir, ignore_errors=True)
