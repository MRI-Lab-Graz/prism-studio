"""
Physio/Eyetracking conversion logic for the Prism Web UI.
Extracted from conversion.py to reduce module size.
"""

from pathlib import Path, PurePosixPath
import io
import re
import shutil
import tempfile
import zipfile
import base64
import logging
import threading
import uuid
from contextlib import nullcontext
from typing import Any
from flask import request, jsonify, session, send_file
from werkzeug.utils import secure_filename

# Shared utilities
from .conversion_job_store import ConversionJobStore
from .conversion_utils import normalize_filename
from src.web.services.project_registration import register_session_in_project

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
        }

        if not config["dry_run"]:
            create_dataset_description(output_dir, name=config["dataset_name"])

            if config["save_to_project"] and not write_direct_to_project:
                p_path = config["project_path"]
                if p_path:
                    project_root = Path(p_path)
                    if project_root.exists():
                        dest_root = config["dest_root"]
                        if dest_root == "rawdata":
                            project_root = project_root / "rawdata"
                        elif dest_root == "sourcedata":
                            project_root = project_root / "sourcedata"
                        project_root.mkdir(parents=True, exist_ok=True)

                        copied_files: list[Path] = []
                        for file in output_dir.rglob("*"):
                            if file.is_file():
                                if _is_job_cancelled(job_id):
                                    for copied_file in copied_files:
                                        copied_file.unlink(missing_ok=True)
                                    _append_job_log(
                                        job_id,
                                        "⏹️ Batch conversion cancelled while copying staged files into the project",
                                        "warning",
                                    )
                                    _batch_job_store.failure(
                                        job_id,
                                        "Cancelled by user",
                                        status="cancelled",
                                    )
                                    return
                                rel_path = file.relative_to(output_dir)
                                dest_file = project_root / rel_path
                                dest_file.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(file, dest_file)
                                copied_files.append(dest_file)

                        # Register each converted session in project.json
                        from collections import defaultdict

                        session_tasks: dict[str, list[str]] = defaultdict(list)
                        for cf in result.converted:
                            if cf.success and cf.session and cf.task:
                                session_tasks[cf.session].append(cf.task)
                        for ses_id, tasks in session_tasks.items():
                            try:
                                register_session_in_project(
                                    Path(p_path),
                                    ses_id,
                                    sorted(set(tasks)),
                                    (
                                        config["modality_filter"]
                                        if config["modality_filter"] != "all"
                                        else "physio"
                                    ),
                                    config["dataset_name"],
                                    "physio",
                                )
                                _append_job_log(
                                    job_id,
                                    f"Registered in project.json: ses-{ses_id} → {', '.join(sorted(set(tasks)))}",
                                    "info",
                                )
                            except Exception as reg_err:
                                _append_job_log(
                                    job_id,
                                    f"⚠️ Could not register session ses-{ses_id} in project.json: {reg_err}",
                                    "warning",
                                )
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
    dest_root = (request.form.get("dest_root") or "root").strip().lower()
    if dest_root == "root":
        dest_root = "prism"
    if dest_root not in {"prism", "rawdata", "sourcedata"}:
        dest_root = "prism"
    sampling_rate_str = request.form.get("sampling_rate", "").strip()
    generate_physio_reports = (
        request.form.get("generate_physio_reports") or "false"
    ).lower() == "true"
    dry_run = (request.form.get("dry_run") or "false").lower() == "true"
    folder_path = request.form.get("folder_path", "").strip()

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
            filename = secure_filename(f.filename)
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

    project_path = session.get("current_project_path")

    _append_job_log(job_id, "🚀 Batch conversion job started", "info")

    config = {
        "tmp_dir": tmp_dir,
        "source_dir": source_dir,
        "sampling_rate": sampling_rate,
        "generate_physio_reports": generate_physio_reports,
        "modality_filter": modality_filter,
        "dry_run": dry_run,
        "dataset_name": dataset_name,
        "save_to_project": save_to_project,
        "dest_root": dest_root,
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
create_dataset_description: Any = None
parse_bids_filename: Any = None
try:
    from src.batch_convert import (
        batch_convert_folder,
        create_dataset_description,
        parse_bids_filename,
    )
except ImportError:
    pass


def check_sourcedata_physio():
    """Check if sourcedata/physio folder exists in current project."""
    try:
        current_project_path = session.get("current_project_path")
        if not current_project_path:
            return jsonify({"exists": False, "message": "No project selected"}), 400

        project_path = Path(current_project_path)
        sourcedata_physio = project_path / "sourcedata" / "physio"

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
                    "path": str(sourcedata_physio) if exists else None,
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

    task = (request.form.get("task") or "rest").strip() or "rest"
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

        try:
            convert_varioport(
                str(input_path),
                str(out_edf),
                str(out_json),
                task_name=task,
                base_freq=base_freq_val,
            )
        except ValueError as e:
            if "Unsupported Varioport header type" in str(e):
                convert_varioport(
                    str(input_path),
                    str(out_edf),
                    str(out_json),
                    task_name=task,
                    base_freq=base_freq_val,
                    allow_raw_multiplexed=True,
                )
            else:
                raise

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
    """Batch convert physio/eyetracking files from a flat folder structure."""
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
    dest_root = (request.form.get("dest_root") or "root").strip().lower()
    if dest_root == "prism":
        dest_root = "root"
    if dest_root not in {"root", "rawdata", "sourcedata"}:
        dest_root = "root"
    flat_structure = (request.form.get("flat_structure") or "false").lower() == "true"
    sampling_rate_str = request.form.get("sampling_rate", "").strip()
    generate_physio_reports = (
        request.form.get("generate_physio_reports") or "false"
    ).lower() == "true"
    dry_run = (request.form.get("dry_run") or "false").lower() == "true"
    folder_path = request.form.get("folder_path", "").strip()

    try:
        sampling_rate = float(sampling_rate_str) if sampling_rate_str else None
    except ValueError:
        return jsonify({"error": "sampling_rate must be a number", "logs": logs}), 400

    files = request.files.getlist("files[]") or request.files.getlist("files")

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
            )

            # If not a dry-run, move files to project if save_to_project is true
            if not dry_run and save_to_project:
                p_path = session.get("current_project_path")
                if p_path:
                    project_root = Path(p_path)
                    if project_root.exists():
                        if dest_root == "rawdata":
                            project_root = project_root / "rawdata"
                        if dest_root == "sourcedata":
                            project_root = project_root / "sourcedata"
                        project_root.mkdir(parents=True, exist_ok=True)
                        # Copy converted files to project
                        for file in output_dir.rglob("*"):
                            if file.is_file():
                                rel_path = file.relative_to(output_dir)
                                dest_file = project_root / rel_path
                                dest_file.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(file, dest_file)

            return jsonify(
                {
                    "converted": result.success_count,
                    "errors": result.error_count,
                    "new_files": result.new_files,
                    "existing_files": result.existing_files,
                    "logs": logs,
                    "dry_run": dry_run,
                }
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    if not files:
        return (
            jsonify(
                {"error": "No files uploaded and no folder path provided", "logs": logs}
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
        filename = secure_filename(f.filename)

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

    if not validated_files:
        return jsonify({"error": "No valid files to convert.", "logs": logs}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_batch_convert_")
    warnings = []
    warned_subjects = set()
    try:
        tmp_path = Path(tmp_dir)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        for f, filename in validated_files:
            f.save(str(input_dir / filename))

        result = batch_convert_folder(
            input_dir,
            output_dir,
            physio_sampling_rate=sampling_rate,
            generate_physio_reports=generate_physio_reports,
            modality_filter=modality_filter,
            log_callback=log_callback,
            dry_run=dry_run,
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

        # Check for conflicts (files with different content)
        if result.conflicts:
            conflicts_info = [
                {"path": str(c.output_path.relative_to(output_dir)), "reason": c.reason}
                for c in result.conflicts
            ]
            return (
                jsonify(
                    {
                        "error": f"File conflicts detected: {len(result.conflicts)} files already exist with different content. Please use different names or delete existing files.",
                        "conflicts": conflicts_info,
                        "logs": logs,
                    }
                ),
                409,
            )

        project_saved = False
        project_root = None
        if save_to_project:
            p_path = session.get("current_project_path")
            if p_path:
                project_root = Path(p_path)
                if project_root.exists():
                    if dest_root == "rawdata":
                        project_root = project_root / "rawdata"
                    if dest_root == "sourcedata":
                        project_root = project_root / "sourcedata"
                    project_root.mkdir(parents=True, exist_ok=True)
                else:
                    warnings.append(
                        f"Project path not found: {p_path}. Copy to project skipped."
                    )
                    project_root = None
            else:
                warnings.append("No active project selected; copy to project skipped.")

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(output_dir)
                    zf.write(file_path, rel_path)

                    if project_root:
                        # Determine destination path based on flat_structure option
                        if flat_structure and dest_root == "sourcedata":
                            # Flat structure: copy files to sourcedata/modality/ without sub-/ses- hierarchy
                            # Determine modality from filename
                            file_modality = (
                                modality_filter
                                if modality_filter != "all"
                                else "physio"
                            )
                            dest_path = project_root / file_modality / rel_path.name
                            log_callback(
                                f"Flat copy: {rel_path.name} → {dest_root}/{file_modality}/{rel_path.name}"
                            )
                        else:
                            # PRISM structure: preserve sub-XXX/ses-YYY/modality/ hierarchy
                            # Warn if subject folder is being created
                            bids = (
                                parse_bids_filename(rel_path.name)
                                if parse_bids_filename
                                else None
                            )
                            subject_label = None
                            if bids and bids.get("sub"):
                                subject_label = bids.get("sub")
                            else:
                                m = re.search(r"(sub-[A-Za-z0-9]+)", rel_path.name)
                                if m:
                                    subject_label = m.group(1)

                            if subject_label:
                                subject_dir = project_root / subject_label
                                if (
                                    not subject_dir.exists()
                                    and subject_label not in warned_subjects
                                ):
                                    warnings.append(
                                        f"Subject folder {subject_label} did not exist and will be created in project."
                                    )
                                    warned_subjects.add(subject_label)

                            dest_path = project_root / rel_path

                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_path)
                        project_saved = True

        if project_saved and not dry_run:
            from collections import defaultdict

            session_tasks: dict[str, list[str]] = defaultdict(list)
            for cf in result.converted:
                if cf.success and cf.session and cf.task:
                    session_tasks[cf.session].append(cf.task)
            p_path = session.get("current_project_path")
            if p_path:
                for ses_id, tasks in session_tasks.items():
                    try:
                        register_session_in_project(
                            Path(p_path),
                            ses_id,
                            sorted(set(tasks)),
                            modality_filter if modality_filter != "all" else "physio",
                            dataset_name,
                            "physio",
                        )
                    except Exception:
                        pass

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
                "warnings": warnings,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e), "logs": logs}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _sanitize_bids_label(raw: str) -> str | None:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", (raw or "").strip())
    return cleaned or None


def _normalize_session_label(raw: str) -> str | None:
    """Normalize session labels to match converter conventions.

    Numeric sessions are zero-padded to two digits ("1" -> "01").
    Non-numeric labels ("post", "baseline", "t1") are preserved.
    """
    cleaned = _sanitize_bids_label(raw)
    if not cleaned:
        return None
    if cleaned.isdigit():
        return f"{int(cleaned):02d}"
    return cleaned


def _extract_subject_session_from_source_path(
    source_path: str,
    subject_level_from_end: int = 2,
    session_level_from_end: int = 1,
    example_path: str = "",
    subject_example_value: str = "",
    session_example_value: str = "",
) -> tuple[str | None, str | None]:
    normalized = (source_path or "").replace("\\", "/")
    parts = [
        part for part in PurePosixPath(normalized).parts[:-1] if part not in {".", ".."}
    ]

    subject_label = None
    session_label = None

    sub_pattern = re.compile(r"^sub[-_]?([A-Za-z0-9]+)$", re.IGNORECASE)
    ses_pattern = re.compile(r"^ses[-_]?([A-Za-z0-9]+)$", re.IGNORECASE)

    for part in parts:
        if subject_label is None:
            sub_match = sub_pattern.match(part)
            if sub_match:
                subject_label = _sanitize_bids_label(sub_match.group(1))
        if session_label is None:
            ses_match = ses_pattern.match(part)
            if ses_match:
                session_label = _normalize_session_label(ses_match.group(1))

    subject_level = max(1, int(subject_level_from_end or 2))
    session_level = max(1, int(session_level_from_end or 1))

    def _split_parent_parts(path_value: str) -> list[str]:
        normalized_path = (path_value or "").replace("\\", "/")
        return [
            part
            for part in PurePosixPath(normalized_path).parts[:-1]
            if part not in {".", ".."}
        ]

    def _part_at_level(parts_list: list[str], level_from_end: int) -> str | None:
        if not parts_list:
            return None
        idx = len(parts_list) - max(1, int(level_from_end))
        if idx < 0:
            idx = 0
        if idx >= len(parts_list):
            return None
        return parts_list[idx]

    def _normalize_entity_label(part_value: str, entity: str) -> str | None:
        if part_value is None:
            return None
        if entity == "subject":
            sub_match = re.match(r"^sub[-_]?([A-Za-z0-9]+)$", part_value, re.IGNORECASE)
            if sub_match:
                return _sanitize_bids_label(sub_match.group(1))
        if entity == "session":
            ses_match = re.match(r"^ses[-_]?([A-Za-z0-9]+)$", part_value, re.IGNORECASE)
            if ses_match:
                return _normalize_session_label(ses_match.group(1))
            return _normalize_session_label(part_value)
        return _sanitize_bids_label(part_value)

    def _extract_by_example(
        source_part: str,
        example_part: str,
        example_value: str,
        entity: str,
    ) -> str | None:
        if source_part is None:
            return None
        if not example_value:
            return _normalize_entity_label(source_part, entity)

        token = (example_value or "").strip()
        if not token:
            return _normalize_entity_label(source_part, entity)

        pos = example_part.find(token) if example_part is not None else -1
        if pos < 0 and example_part is not None:
            lower_pos = example_part.lower().find(token.lower())
            pos = lower_pos

        if pos < 0:
            return _normalize_entity_label(source_part, entity)

        prefix = example_part[:pos]
        suffix = example_part[pos + len(token) :]

        candidate = source_part
        if prefix and candidate.startswith(prefix):
            candidate = candidate[len(prefix) :]
        if suffix and candidate.endswith(suffix):
            candidate = candidate[: -len(suffix)]

        return _normalize_entity_label(candidate, entity)

    src_parts = _split_parent_parts(source_path)
    ex_parts = _split_parent_parts(example_path) if example_path else []

    source_subject_part = _part_at_level(src_parts, subject_level)
    source_session_part = _part_at_level(src_parts, session_level)
    example_subject_part = _part_at_level(ex_parts, subject_level) if ex_parts else ""
    example_session_part = _part_at_level(ex_parts, session_level) if ex_parts else ""

    if source_subject_part is not None:
        subject_label = _extract_by_example(
            source_subject_part,
            example_subject_part or source_subject_part,
            (subject_example_value or "").strip(),
            "subject",
        )

    session_token = (session_example_value or "").strip()
    if session_token and source_session_part is not None:
        session_label = _extract_by_example(
            source_session_part,
            example_session_part or source_session_part,
            session_token,
            "session",
        )

    if subject_label is None and parts:
        subject_idx = len(parts) - subject_level
        if subject_idx < 0:
            subject_idx = 0
        subject_label = _sanitize_bids_label(parts[subject_idx])

    if session_label is None and parts:
        session_idx = len(parts) - session_level
        if session_idx < 0:
            session_idx = 0
        if subject_label is not None and len(parts) == 1:
            session_label = None
        elif session_idx < len(parts):
            candidate = _sanitize_bids_label(parts[session_idx])
            if candidate is not None and candidate != subject_label:
                session_label = _normalize_session_label(candidate)

    return subject_label, session_label


def _apply_folder_placeholders(
    name_template: str,
    source_path: str,
    subject_level_from_end: int = 2,
    session_level_from_end: int = 1,
    example_path: str = "",
    subject_example_value: str = "",
    session_example_value: str = "",
) -> str:
    subject_label, session_label = _extract_subject_session_from_source_path(
        source_path,
        subject_level_from_end=subject_level_from_end,
        session_level_from_end=session_level_from_end,
        example_path=example_path,
        subject_example_value=subject_example_value,
        session_example_value=session_example_value,
    )

    if "{subject}" in name_template and not subject_label:
        raise ValueError("Could not extract subject from folder path")

    resolved = name_template.replace("{subject}", subject_label or "")

    if "{session}" in resolved:
        if session_label:
            resolved = resolved.replace("{session}", session_label)
        else:
            resolved = resolved.replace("_ses-{session}", "")
            resolved = resolved.replace("ses-{session}_", "")
            resolved = resolved.replace("ses-{session}", "")
            resolved = resolved.replace("{session}", "")

    resolved = re.sub(r"__+", "_", resolved)
    return re.sub(r"^_+|_+$", "", resolved)


def api_physio_rename():
    """Rename uploaded files based on a regex pattern and return a ZIP."""
    pattern = request.form.get("pattern", "")
    replacement = request.form.get("replacement", "")
    dry_run = request.form.get("dry_run", "false").lower() == "true"
    organize = request.form.get("organize", "false").lower() == "true"
    modality = request.form.get("modality", "physio")
    save_to_project = request.form.get("save_to_project", "false").lower() == "true"
    skip_zip = request.form.get("skip_zip", "false").lower() == "true"
    dest_root = (request.form.get("dest_root") or "root").strip().lower()
    if dest_root == "root":
        dest_root = "prism"
    if dest_root not in {"prism", "rawdata", "sourcedata"}:
        dest_root = "prism"
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

    files = request.files.getlist("files[]") or request.files.getlist("files")
    filenames = request.form.getlist("filenames[]") or request.form.getlist("filenames")
    source_paths = request.form.getlist("source_paths[]") or request.form.getlist(
        "source_paths"
    )

    if not files and not filenames and not dry_run:
        return jsonify({"error": "No files or filenames provided"}), 400

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return jsonify({"error": f"Invalid regex: {str(e)}"}), 400

    results = []
    warnings = []
    warned_subjects = set()

    if dry_run:
        source_names = (
            filenames if filenames else [f.filename for f in files if f.filename]
        )
        for idx, fname in enumerate(source_names):
            source_path = source_paths[idx] if idx < len(source_paths) else fname
            try:
                raw_name = Path(source_path).name
                new_name = regex.sub(replacement, raw_name)
                if id_source == "folder":
                    new_name = _apply_folder_placeholders(
                        new_name,
                        source_path,
                        subject_level_from_end=folder_subject_level,
                        session_level_from_end=folder_session_level,
                        example_path=folder_example_path,
                        subject_example_value=folder_subject_value,
                        session_example_value=folder_session_value,
                    )
                new_name = normalize_filename(new_name)

                zip_path = new_name
                if organize:
                    bids = (
                        parse_bids_filename(new_name) if parse_bids_filename else None
                    )
                    if bids:
                        sub = bids.get("sub")
                        ses = bids.get("ses")
                        parts = [sub]
                        if ses:
                            parts.append(ses)
                        parts.append(modality)
                        parts.append(new_name)
                        zip_path = "/".join(parts)

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

    if not files:
        return jsonify({"error": "No files uploaded for renaming"}), 400

    mem = io.BytesIO() if not skip_zip else None
    project_root = None
    if save_to_project:
        p_path = session.get("current_project_path")
        if p_path:
            project_root = Path(p_path)
            if project_root.exists():
                if dest_root == "rawdata":
                    project_root = project_root / "rawdata"
                if dest_root == "sourcedata":
                    project_root = project_root / "sourcedata"
                project_root.mkdir(parents=True, exist_ok=True)
            else:
                warnings.append(
                    f"Project path not found: {p_path}. Copy to project skipped."
                )
                project_root = None
        else:
            warnings.append("No active project selected; copy to project skipped.")

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
                old_name = Path(source_path).name

                try:
                    new_name = regex.sub(replacement, old_name)
                    if id_source == "folder":
                        new_name = _apply_folder_placeholders(
                            new_name,
                            source_path,
                            subject_level_from_end=folder_subject_level,
                            session_level_from_end=folder_session_level,
                            example_path=folder_example_path,
                            subject_example_value=folder_subject_value,
                            session_example_value=folder_session_value,
                        )
                    new_name = normalize_filename(new_name)

                    zip_path = new_name
                    if organize:
                        bids = (
                            parse_bids_filename(new_name)
                            if parse_bids_filename
                            else None
                        )
                        if bids:
                            sub = bids.get("sub")
                            ses = bids.get("ses")
                            parts = [sub]
                            if ses:
                                parts.append(ses)
                            parts.append(modality)
                            parts.append(new_name)
                            zip_path = "/".join(parts)

                    f_content = f.read()
                    if zf is not None:
                        zf.writestr(zip_path, f_content)

                    if project_root:
                        if flat_structure and dest_root == "sourcedata":
                            dest_path = project_root / modality / new_name
                        else:
                            dest_path = project_root / Path(zip_path)

                            subject_label = None
                            if parse_bids_filename:
                                bids_parts = parse_bids_filename(new_name)
                                if bids_parts:
                                    subject_label = bids_parts.get("sub")
                            if not subject_label:
                                m = re.search(r"(sub-[A-Za-z0-9]+)", new_name)
                                if m:
                                    subject_label = m.group(1)

                            if subject_label:
                                subject_dir = project_root / subject_label
                                if (
                                    not subject_dir.exists()
                                    and subject_label not in warned_subjects
                                ):
                                    warnings.append(
                                        f"Subject folder {subject_label} did not exist and will be created in project."
                                    )
                                    warned_subjects.add(subject_label)

                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(dest_path, "wb") as out_f:
                            out_f.write(f_content)

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

        zip_base64 = None
        if not skip_zip and mem is not None:
            mem.seek(0)
            zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        return jsonify(
            {
                "status": "success",
                "results": results,
                "zip": zip_base64,
                "project_saved": bool(project_root),
                "warnings": warnings,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
