import io
import os
import tempfile
import zipfile
from pathlib import Path

from flask import jsonify, request, send_file
from src.methods_boilerplate import write_methods_boilerplate
from src.survey_columns import detect_columns


def _require_json_object_payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (
            jsonify({"error": "Invalid JSON payload. Expected an object."}),
            400,
        )
    return data, None


def _extract_file_paths(files_payload: object) -> list[str]:
    if not isinstance(files_payload, list):
        return []

    file_paths: list[str] = []
    for file_obj in files_payload:
        candidate = file_obj.get("path") if isinstance(file_obj, dict) else file_obj
        if not isinstance(candidate, str):
            continue
        candidate = candidate.strip()
        if candidate:
            file_paths.append(candidate)
    return file_paths


def handle_generate_lss_endpoint():
    """Generate LSS from selected JSON files."""
    try:
        from src.limesurvey_exporter import generate_lss
    except ImportError:
        generate_lss = None

    if not generate_lss:
        return jsonify({"error": "LSS exporter not available"}), 500

    try:
        data, payload_error = _require_json_object_payload()
        if payload_error is not None:
            return payload_error

        file_paths = _extract_file_paths(data.get("files", []))
        if not file_paths:
            return jsonify({"error": "No files selected"}), 400

        # Entries carry the ticked questions (include), matrix and run settings;
        # generate_lss honours them, so hand it the whole entry, not just the path.
        entries = {
            e["path"].strip(): e for e in data.get("files", []) if isinstance(e, dict) and isinstance(e.get("path"), str)
        }
        # The toolbar's matrix switch is a master switch: off means off for every file.
        master_matrix = bool(data.get("matrix", True))
        valid_files = [
            {
                **entries[p],
                "path": p,
                "matrix": bool(entries[p].get("matrix", True)) and master_matrix,
            }
            if p in entries
            else p
            for p in file_paths
            if os.path.exists(p)
        ]
        if not valid_files:
            return jsonify({"error": "No valid files found"}), 404

        fd, temp_path = tempfile.mkstemp(suffix=".lss")
        os.close(fd)

        language = data.get("language", "en")
        languages = data.get("languages") or [language]
        base_language = data.get("base_language") or language
        survey_title = data.get("survey_title", "")
        matrix_mode = bool(data.get("matrix", True))
        matrix_global = bool(data.get("matrix_global", True))
        try:
            generate_lss(
                valid_files,
                temp_path,
                language=language,
                languages=languages,
                base_language=base_language,
                matrix_mode=matrix_mode,
                matrix_global=matrix_global,
            )
            lss_bytes = Path(temp_path).read_bytes()
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

        import re
        from datetime import datetime

        date_str = datetime.now().strftime("%Y-%m-%d")
        if survey_title:
            safe_title = re.sub(r"[^\w\s-]", "", survey_title)
            safe_title = re.sub(r"[\s]+", "_", safe_title).strip("_")
            download_filename = f"{safe_title}_{date_str}.lss"
        else:
            download_filename = f"survey_export_{date_str}.lss"

        return send_file(
            io.BytesIO(lss_bytes),
            as_attachment=True,
            download_name=download_filename,
            mimetype="application/xml",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_generate_pavlovia_endpoint():
    """Generate a Pavlovia/PsychoPy experiment .zip from a selected PRISM JSON file."""
    try:
        from src.converters.pavlovia import export_to_pavlovia
    except ImportError:
        export_to_pavlovia = None

    if not export_to_pavlovia:  # type: ignore[truthy-function]
        return jsonify({"error": "Pavlovia exporter not available"}), 500

    try:
        data, payload_error = _require_json_object_payload()
        if payload_error is not None:
            return payload_error

        file_paths = _extract_file_paths(data.get("files", []))
        if not file_paths:
            return jsonify({"error": "No files selected"}), 400
        if len(file_paths) > 1:
            return jsonify(
                {"error": "Pavlovia export supports one survey file at a time"}
            ), 400

        json_path = Path(file_paths[0])
        if not json_path.exists():
            return jsonify({"error": "File not found"}), 404

        experiment_name = data.get("experiment_name") or None
        language = data.get("base_language") or data.get("language")
        first = data["files"][0] if isinstance(data.get("files"), list) else None
        include = first.get("include") if isinstance(first, dict) else None

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "export"
            export_to_pavlovia(
                json_path, output_dir, experiment_name, language=language, include=include
            )

            zip_fd, zip_path = tempfile.mkstemp(suffix=".zip")
            os.close(zip_fd)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in output_dir.rglob("*"):
                    if file_path.is_file():
                        zf.write(file_path, file_path.relative_to(output_dir))

            download_filename = f"{output_dir.name}_pavlovia.zip"

        response = send_file(
            zip_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype="application/zip",
        )
        response.call_on_close(lambda: os.unlink(zip_path))
        return response
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def handle_generate_boilerplate_endpoint():
    """Generate Methods Boilerplate from selected JSON files."""
    try:
        data, payload_error = _require_json_object_payload()
        if payload_error is not None:
            return payload_error

        file_paths = _extract_file_paths(data.get("files", []))
        if not file_paths:
            return jsonify({"error": "No files selected"}), 400

        valid_files = [
            file_path for file_path in file_paths if os.path.exists(file_path)
        ]
        if not valid_files:
            return jsonify({"error": "No valid files found"}), 404

        fd, temp_path = tempfile.mkstemp(suffix=".md")
        os.close(fd)

        language = data.get("language", "en")
        write_methods_boilerplate(valid_files, temp_path, lang=language)

        with open(temp_path, "r", encoding="utf-8") as file_handle:
            md_content = file_handle.read()

        html_path = Path(temp_path).with_suffix(".html")
        html_content = ""
        if html_path.exists():
            with open(html_path, "r", encoding="utf-8") as file_handle:
                html_content = file_handle.read()

        try:
            os.remove(temp_path)
            if html_path.exists():
                os.remove(html_path)
        except Exception:
            pass

        return jsonify(
            {
                "md": md_content,
                "html": html_content,
                "filename_base": f"methods_boilerplate_{language}",
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_detect_columns():
    """Detect column names from uploaded file for ID column selection."""
    file = request.files.get("file")
    source_file_path = (request.form.get("source_file_path") or "").strip()
    options = {
        "separator": request.form.get("separator"),
        "session_column_override": (request.form.get("session_column_override") or "").strip(),
        "run_column_override": (request.form.get("run_column_override") or "").strip(),
    }

    try:
        if file and getattr(file, "filename", ""):
            with tempfile.TemporaryDirectory(prefix="prism_detect_cols_") as tmp_dir:
                upload = Path(tmp_dir) / Path(file.filename).name
                file.save(str(upload))
                return jsonify(detect_columns(upload, **options))
        if source_file_path:
            source = Path(source_file_path).expanduser().resolve()
            if not source.is_file():
                return jsonify({"error": f"File not found: {source_file_path}"}), 400
            return jsonify(detect_columns(source, **options))
        return jsonify({"error": "No file uploaded"}), 400
    except ValueError as e:  # a file that cannot be read
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"ERROR in /api/detect-columns: {e}")
        return jsonify({"error": str(e)}), 500
