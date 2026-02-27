"""
Physio/Eyetracking conversion logic for the Prism Web UI.
Extracted from conversion.py to reduce module size.
"""

import io
import re
import shutil
import tempfile
import zipfile
import base64
import logging
from pathlib import Path
from typing import Any
from flask import request, jsonify, session, send_file
from werkzeug.utils import secure_filename

# Shared utilities
from .conversion_utils import normalize_filename

# Optional dependencies
convert_varioport: Any = None
try:
    from helpers.physio.convert_varioport import convert_varioport
except ImportError:
    pass

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
    except Exception as e:
        return jsonify({"exists": False, "error": str(e)}), 500


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

        convert_varioport(
            str(input_path),
            str(out_edf),
            str(out_json),
            task_name=task,
            base_freq=base_freq_val,
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
    if dest_root == "rawdata":
        dest_root = "root"
    if dest_root not in {"root", "sourcedata"}:
        dest_root = "root"
    flat_structure = (request.form.get("flat_structure") or "false").lower() == "true"
    sampling_rate_str = request.form.get("sampling_rate", "").strip()
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

        import base64

        zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        return jsonify(
            {
                "status": "success",
                "log": "\n".join([log_entry["message"] for log_entry in logs]),
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


def api_physio_rename():
    """Rename uploaded files based on a regex pattern and return a ZIP."""
    pattern = request.form.get("pattern", "")
    replacement = request.form.get("replacement", "")
    dry_run = request.form.get("dry_run", "false").lower() == "true"
    organize = request.form.get("organize", "false").lower() == "true"
    modality = request.form.get("modality", "physio")
    save_to_project = request.form.get("save_to_project", "false").lower() == "true"
    dest_root = (request.form.get("dest_root") or "root").strip().lower()
    if dest_root == "rawdata":
        dest_root = "root"
    if dest_root not in {"root", "sourcedata"}:
        dest_root = "root"
    flat_structure = (request.form.get("flat_structure") or "false").lower() == "true"

    files = request.files.getlist("files[]") or request.files.getlist("files")

    # If dry run, we might just have filenames in a list
    filenames = request.form.getlist("filenames[]") or request.form.getlist("filenames")

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
        # Use filenames if provided, else use uploaded files' names
        source_names = (
            filenames if filenames else [f.filename for f in files if f.filename]
        )
        for fname in source_names:
            try:
                raw_name = Path(fname).name
                new_name = regex.sub(replacement, raw_name)
                new_name = normalize_filename(new_name)

                # Determine the path within the ZIP (for preview)
                zip_path = new_name
                if organize:
                    bids = None
                    if parse_bids_filename:
                        bids = parse_bids_filename(new_name)

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
                    {"old": fname, "new": new_name, "path": zip_path, "success": True}
                )
            except Exception as e:
                results.append({"old": fname, "new": str(e), "success": False})
        return jsonify({"results": results, "warnings": warnings})

    # Actual renaming and zipping
    if not files:
        return jsonify({"error": "No files uploaded for renaming"}), 400

    mem = io.BytesIO()
    project_root = None
    if save_to_project:
        p_path = session.get("current_project_path")
        if p_path:
            project_root = Path(p_path)
            if project_root.exists():
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
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                if not f or not f.filename:
                    continue
                old_name = Path(f.filename).name

                try:
                    new_name = regex.sub(replacement, old_name)
                    new_name = normalize_filename(new_name)

                    # Determine the path within the ZIP
                    zip_path = new_name
                    if organize:
                        # Try to parse BIDS components to build structure
                        bids = None
                        if parse_bids_filename:
                            bids = parse_bids_filename(new_name)

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
                    zf.writestr(zip_path, f_content)

                    if project_root:
                        # Determine destination path based on flat_structure option
                        if flat_structure and dest_root == "sourcedata":
                            # Flat structure: copy files to sourcedata/modality/ without sub-/ses- hierarchy
                            dest_path = project_root / modality / new_name
                        else:
                            # PRISM structure: preserve sub-XXX/ses-YYY/modality/ hierarchy
                            dest_path = project_root / Path(zip_path)

                            # Warn if subject folder does not yet exist (but still allow creation)
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
                            "old": old_name,
                            "new": new_name,
                            "success": True,
                            "path": zip_path,
                        }
                    )
                except Exception as e:
                    results.append({"old": old_name, "new": str(e), "success": False})

        mem.seek(0)
        import base64

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
