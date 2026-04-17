from flask import Blueprint, jsonify, request, send_file, session
from pathlib import Path
import atexit
import json
import os
import subprocess
import sys
import tempfile
import threading
import traceback
import uuid
from threading import Lock
from typing import Dict, Optional
from src.cross_platform import safe_path_join
from .projects_helpers import _resolve_project_root_path

projects_export_bp = Blueprint("projects_export", __name__)

# ---------------------------------------------------------------------------
# Async export job store
# ---------------------------------------------------------------------------

_export_jobs: Dict[str, dict] = {}
_export_lock = Lock()


def _cleanup_all_export_temps() -> None:
    """Called at process exit: remove any cancelled/errored ZIP leftovers."""
    with _export_lock:
        for job in _export_jobs.values():
            if job.get("status") in ("cancelled", "error"):
                zip_path = job.get("zip_path")
                if zip_path and os.path.exists(zip_path):
                    try:
                        os.unlink(zip_path)
                    except OSError:
                        pass


atexit.register(_cleanup_all_export_temps)


def _create_export_job(job_id: str) -> None:
    with _export_lock:
        _export_jobs[job_id] = {
            "status": "pending",
            "percent": 0,
            "message": "Starting...",
            "zip_path": None,
            "filename": None,
            "error": None,
            "cancel_event": threading.Event(),
        }


def _update_export_job(job_id: str, **kwargs: object) -> None:
    with _export_lock:
        if job_id in _export_jobs:
            _export_jobs[job_id].update(kwargs)


def _get_export_job(job_id: str) -> dict:
    with _export_lock:
        job = _export_jobs.get(job_id)
        if job is None:
            return {}
        return {k: v for k, v in job.items() if k not in ("cancel_event",)}


def _run_export_job(job_id: str, export_kwargs: dict, filename: str, output_folder: Optional[str] = None) -> None:
    """Background thread: run export_project and update job store."""
    from src.web.export_project import export_project as do_export

    # Write ZIP to the requested output folder, or next to the project on disk
    project_path: Path = export_kwargs["project_path"]
    if output_folder:
        dest_dir = Path(output_folder)
    else:
        dest_dir = project_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    output_zip = dest_dir / filename

    completed_ok = False
    try:
        job = _export_jobs.get(job_id, {})
        cancel_event = job.get("cancel_event")

        def progress_callback(percent: int, message: str) -> None:
            _update_export_job(job_id, percent=percent, message=message, status="running")

        do_export(
            **export_kwargs,
            output_zip=output_zip,
            progress_callback=progress_callback,
            cancelled_flag=cancel_event,
        )

        if cancel_event and cancel_event.is_set():
            _update_export_job(job_id, status="cancelled", message="Export cancelled", percent=0)
            output_zip.unlink(missing_ok=True)
        else:
            completed_ok = True
            _update_export_job(
                job_id,
                status="complete",
                percent=100,
                message="Export complete",
                zip_path=str(output_zip),
                filename=filename,
            )
    except InterruptedError:
        _update_export_job(job_id, status="cancelled", message="Export cancelled", percent=0)
        output_zip.unlink(missing_ok=True)
    except Exception as exc:
        _update_export_job(job_id, status="error", message=str(exc), error=str(exc))
        output_zip.unlink(missing_ok=True)
    finally:
        # Nothing extra to clean up — ZIP lives at user-chosen path, not a temp file
        pass


@projects_export_bp.route("/api/projects/export", methods=["POST"])
def export_project():
    """
    Export the current project as a ZIP file with optional anonymization.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "anonymize": true,
        "mask_questions": true,
        "include_derivatives": true,
        "include_code": true,
        "include_analysis": false
    }
    """
    from src.web.export_project import export_project as do_export

    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"error": "No data provided"}), 400

        project_path = data.get("project_path")
        resolved_project_path = _resolve_project_root_path(project_path)
        if resolved_project_path is None:
            return jsonify({"error": "Invalid project path"}), 400

        project_path = resolved_project_path

        # Get export options
        anonymize = bool(data.get("anonymize", True))
        mask_questions = bool(data.get("mask_questions", True))
        # Keep anonymization settings simple in UI: fixed random IDs when enabled.
        id_length = 8
        deterministic = False
        include_derivatives = bool(data.get("include_derivatives", True))
        include_code = bool(data.get("include_code", True))
        include_analysis = bool(data.get("include_analysis", False))
        scrub_mri_json = bool(data.get("scrub_mri_json", False))

        # Create temporary file for ZIP
        temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
        os.close(temp_fd)

        try:
            # Perform export
            do_export(
                project_path=project_path,
                output_zip=Path(temp_path),
                anonymize=anonymize,
                mask_questions=mask_questions,
                id_length=id_length,
                deterministic=deterministic,
                include_derivatives=include_derivatives,
                include_code=include_code,
                include_analysis=include_analysis,
                scrub_mri_json=scrub_mri_json,
            )

            # Generate filename
            project_name = project_path.name
            anon_suffix = "_anonymized" if anonymize else ""
            filename = f"{project_name}{anon_suffix}_export.zip"

            # Send file
            return send_file(
                temp_path,
                mimetype="application/zip",
                as_attachment=True,
                download_name=filename,
            )

        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/structure", methods=["POST"])
def export_project_structure():
    """Return available sessions and modalities for the given project."""
    try:
        from src.project_structure import get_project_modalities_and_sessions
        data = request.get_json() or {}
        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"error": "Invalid project path"}), 400
        structure = get_project_modalities_and_sessions(resolved)
        return jsonify({"success": True, **structure})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/browse-folder", methods=["POST"])
def export_browse_folder():
    """Open a native folder-picker dialog and return the chosen path."""
    from src.web.services import file_picker
    outcome = file_picker.pick_folder()
    if outcome.error:
        return jsonify({"folder": None, "error": outcome.error}), outcome.status_code
    return jsonify({"folder": outcome.path or None})


@projects_export_bp.route("/api/projects/export/defacing-report", methods=["POST"])
def export_defacing_report():
    """Return a defacing status report for all anatomical scans in the project."""
    try:
        from src.mri_json_scrubber import build_defacing_report

        data = request.get_json() or {}
        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"error": "Invalid project path"}), 400

        report = build_defacing_report(resolved)
        counts = {"defaced": 0, "not_defaced": 0, "unknown": 0}
        for entry in report:
            status = entry.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1

        return jsonify({"success": True, "report": report, "counts": counts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/start", methods=["POST"])
def export_project_start():
    """Start an async export job. Returns {job_id}."""
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"error": "No data provided"}), 400

        project_path_raw = data.get("project_path")
        resolved = _resolve_project_root_path(project_path_raw)
        if resolved is None:
            return jsonify({"error": "Invalid project path"}), 400

        anonymize = bool(data.get("anonymize", True))
        mask_questions = bool(data.get("mask_questions", True))
        include_derivatives = bool(data.get("include_derivatives", True))
        include_code = bool(data.get("include_code", True))
        include_analysis = bool(data.get("include_analysis", False))
        scrub_mri_json = bool(data.get("scrub_mri_json", False))
        output_folder: Optional[str] = data.get("output_folder") or None

        # Optional session / modality / acq filters
        exclude_sessions_list = data.get("exclude_sessions") or []
        exclude_modalities_list = data.get("exclude_modalities") or []
        # exclude_acq: dict of {modality: [acq_label, ...]} from client
        exclude_acq_raw = data.get("exclude_acq") or {}
        exclude_acq = {mod: set(labels) for mod, labels in exclude_acq_raw.items() if labels} if exclude_acq_raw else None

        project_name = resolved.name
        anon_suffix = "_anonymized" if anonymize else ""
        filename = f"{project_name}{anon_suffix}_export.zip"

        export_kwargs = {
            "project_path": resolved,
            "anonymize": anonymize,
            "mask_questions": mask_questions,
            "id_length": 8,
            "deterministic": False,
            "include_derivatives": include_derivatives,
            "include_code": include_code,
            "include_analysis": include_analysis,
            "scrub_mri_json": scrub_mri_json,
            "exclude_sessions": set(exclude_sessions_list) if exclude_sessions_list else None,
            "exclude_modalities": set(exclude_modalities_list) if exclude_modalities_list else None,
            "exclude_acq": exclude_acq,
        }

        job_id = str(uuid.uuid4())
        _create_export_job(job_id)

        t = threading.Thread(
            target=_run_export_job,
            args=(job_id, export_kwargs, filename, output_folder),
            daemon=True,
        )
        t.start()

        return jsonify({"job_id": job_id})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@projects_export_bp.route("/api/projects/export/<job_id>/status", methods=["GET"])
def export_job_status(job_id: str):
    """Poll export job status. Returns {status, percent, message, zip_path}."""
    job = _get_export_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status": job.get("status"),
        "percent": job.get("percent", 0),
        "message": job.get("message", ""),
        "error": job.get("error"),
        "zip_path": job.get("zip_path"),
    })


@projects_export_bp.route("/api/projects/export/<job_id>/download", methods=["GET"])
def export_job_download(job_id: str):
    """Download the completed export ZIP and clean up job."""
    job = _get_export_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job.get("status") != "complete":
        return jsonify({"error": "Export not complete"}), 400

    zip_path = job.get("zip_path")
    filename = job.get("filename", "export.zip")

    if not zip_path or not os.path.exists(zip_path):
        return jsonify({"error": "Export file not found"}), 404

    # Send file then schedule cleanup
    def _cleanup() -> None:
        try:
            if os.path.exists(zip_path):
                os.unlink(zip_path)
        except Exception:
            pass
        with _export_lock:
            _export_jobs.pop(job_id, None)

    response = send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )
    # Schedule cleanup after response is sent
    threading.Thread(target=_cleanup, daemon=True).start()
    return response


@projects_export_bp.route("/api/projects/export/<job_id>/cancel", methods=["DELETE"])
def export_job_cancel(job_id: str):
    """Request cancellation of a running export job."""
    with _export_lock:
        job = _export_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    cancel_event = job.get("cancel_event")
    if cancel_event:
        cancel_event.set()
    return jsonify({"cancelled": True})


@projects_export_bp.route("/api/projects/anc-export", methods=["POST"])
def anc_export_project():
    """
    Export the current project to ANC (Austrian NeuroCloud) compatible format.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "convert_to_git_lfs": false,
        "include_ci_examples": false,
        "metadata": {
            "DATASET_NAME": "My Study",
            "CONTACT_EMAIL": "contact@example.com",
            "AUTHOR_GIVEN_NAME": "John",
            "AUTHOR_FAMILY_NAME": "Doe",
            "DATASET_ABSTRACT": "Description of the dataset"
        }
    }
    """
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        project_path = data.get("project_path")
        resolved_project_path = _resolve_project_root_path(project_path)
        if resolved_project_path is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        project_path = resolved_project_path

        # Import AND exporter
        from src.converters.anc_export import ANCExporter

        # Get export options
        convert_to_git_lfs = bool(data.get("convert_to_git_lfs", False))
        include_ci_examples = bool(data.get("include_ci_examples", False))
        metadata = data.get("metadata", {})

        # Determine output path
        output_path = project_path.parent / f"{project_path.name}_anc_export"

        # Create exporter
        exporter = ANCExporter(project_path, output_path)

        # Perform export
        result_path = exporter.export(
            metadata=metadata,
            convert_to_git_lfs=convert_to_git_lfs,
            include_ci_examples=include_ci_examples,
            copy_data=True,
        )

        return jsonify(
            {
                "success": True,
                "output_path": str(result_path),
                "message": "ANC export completed successfully",
                "generated_files": {
                    "readme": str(result_path / "README.md"),
                    "citation": str(result_path / "CITATION.cff"),
                    "validator_config": str(
                        result_path / ".bids-validator-config.json"
                    ),
                },
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@projects_export_bp.route("/api/projects/openminds-tasks", methods=["GET"])
def openminds_get_tasks():
    """Return task names from the current project for the openMINDS pre-flight form."""
    try:
        project_path_value = request.args.get("project_path") or session.get(
            "current_project_path"
        )
        resolved = _resolve_project_root_path(project_path_value)
        if resolved is None:
            return jsonify({"success": False, "error": "No active project"}), 400

        project_json = resolved / "project.json"
        if not project_json.exists():
            return jsonify({"success": True, "tasks": []})

        with open(project_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        task_names = sorted(data.get("TaskDefinitions", {}).keys())
        return jsonify({"success": True, "tasks": task_names})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def _patch_openminds_descriptions(
    output_path: Path, protocol_descriptions: dict
) -> None:
    """Post-process a bids2openminds .jsonld file to fill in behavioral protocol descriptions."""
    if not output_path.exists() or not protocol_descriptions:
        return

    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    modified = False

    def _str_val(v):
        if isinstance(v, str):
            return v
        if isinstance(v, list) and len(v) == 1 and isinstance(v[0], dict):
            return v[0].get("@value", "")
        if isinstance(v, dict):
            return v.get("@value", "")
        return ""

    def _set_val(node, key, new_val):
        old = node[key]
        if isinstance(old, list) and len(old) == 1 and isinstance(old[0], dict):
            old[0]["@value"] = new_val
        elif isinstance(old, dict):
            old["@value"] = new_val
        else:
            node[key] = new_val

    def _patch_node(node):
        nonlocal modified
        if not isinstance(node, dict):
            return

        name_val = None
        desc_key = None

        for k, v in node.items():
            k_lower = k.lower()
            if (
                k_lower in ("name",)
                or k_lower.endswith("/name")
                or k_lower.endswith(":name")
            ):
                sv = _str_val(v)
                if sv:
                    name_val = sv
            if (
                k_lower in ("description",)
                or k_lower.endswith("/description")
                or k_lower.endswith(":description")
            ):
                if _str_val(v) == "To be defined":
                    desc_key = k

        if name_val and desc_key and name_val in protocol_descriptions:
            new_desc = protocol_descriptions[name_val].strip()
            if new_desc:
                _set_val(node, desc_key, new_desc)
                modified = True

    graph = data.get("@graph", [])
    if isinstance(graph, list):
        for node in graph:
            _patch_node(node)
    else:
        _patch_node(data)

    if modified:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


@projects_export_bp.route("/api/projects/openminds-export", methods=["POST"])
def openminds_export_project():
    """
    Export the current project to openMINDS metadata format using bids2openminds.

    Expected JSON body:
    {
        "project_path": "/path/to/project",
        "single_file": true,
        "include_empty": false
    }
    """
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        project_path = data.get("project_path")
        resolved_project_path = _resolve_project_root_path(project_path)
        if resolved_project_path is None:
            return jsonify({"success": False, "error": "Invalid project path"}), 400

        project_path = resolved_project_path

        # Locate bids2openminds CLI (prefer same venv as current Python)
        python_bin_dir = str(Path(sys.executable).parent)
        bids2openminds_cmd = safe_path_join(python_bin_dir, "bids2openminds")
        if not Path(bids2openminds_cmd).is_file():
            # Fall back to PATH
            import shutil

            bids2openminds_cmd = shutil.which("bids2openminds")

        if not bids2openminds_cmd:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": (
                            "bids2openminds is not installed. "
                            "Install it with: pip install bids2openminds"
                        ),
                    }
                ),
                500,
            )

        # Get options
        single_file = bool(data.get("single_file", True))
        include_empty = bool(data.get("include_empty", False))
        supplements = data.get("supplements", {})

        # Determine output path
        project_name = project_path.name
        if single_file:
            output_path = project_path.parent / f"{project_name}_openminds.jsonld"
        else:
            output_path = project_path.parent / f"{project_name}_openminds"

        # Build command
        cmd = [
            bids2openminds_cmd,
            str(project_path),
            "-o",
            str(output_path),
            "--single-file" if single_file else "--multiple-files",
            "--quiet",
        ]
        if include_empty:
            cmd.append("--include-empty-properties")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            error_msg = (
                result.stderr or result.stdout or "bids2openminds conversion failed"
            ).strip()
            return jsonify({"success": False, "error": error_msg}), 500

        # Post-process: patch behavioral protocol descriptions if provided
        protocol_descriptions = supplements.get("protocol_descriptions", {})
        if protocol_descriptions and single_file and output_path.exists():
            _patch_openminds_descriptions(output_path, protocol_descriptions)

        # Write a notes file for ethics/other supplements that can't be auto-patched
        notes = {}
        ethics_category = supplements.get("ethics_category", "").strip()
        if ethics_category:
            notes["ethics_assessment"] = ethics_category
        if notes and single_file:
            notes_path = output_path.parent / (output_path.stem + "_supplements.json")
            with open(notes_path, "w", encoding="utf-8") as f:
                json.dump(notes, f, indent=2, ensure_ascii=False)

        return jsonify(
            {
                "success": True,
                "output_path": str(output_path),
                "single_file": single_file,
                "message": "openMINDS export completed successfully",
                "has_notes": bool(notes),
            }
        )

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Export timed out (>5 min)"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
