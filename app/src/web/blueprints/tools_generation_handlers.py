import os
import sys
import tempfile
from pathlib import Path

from flask import current_app, jsonify, request, send_file


def handle_generate_lss_endpoint():
    """Generate LSS from selected JSON files."""
    try:
        from src.limesurvey_exporter import generate_lss
    except ImportError:
        generate_lss = None

    if not generate_lss:
        return jsonify({"error": "LSS exporter not available"}), 500

    try:
        data = request.get_json()
        files = data.get("files", [])
        if not files:
            return jsonify({"error": "No files selected"}), 400

        valid_files = [
            file_obj
            for file_obj in files
            if os.path.exists(file_obj.get("path") if isinstance(file_obj, dict) else file_obj)
        ]
        if not valid_files:
            return jsonify({"error": "No valid files found"}), 404

        fd, temp_path = tempfile.mkstemp(suffix=".lss")
        os.close(fd)

        language = data.get("language", "en")
        languages = data.get("languages") or [language]
        base_language = data.get("base_language") or language
        ls_version = data.get("ls_version", "3")
        survey_title = data.get("survey_title", "")
        generate_lss(
            valid_files,
            temp_path,
            language=language,
            languages=languages,
            base_language=base_language,
            ls_version=ls_version,
        )

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
            temp_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype="application/xml",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_generate_boilerplate_endpoint():
    """Generate Methods Boilerplate from selected JSON files."""
    try:
        root_dir = str(Path(current_app.root_path))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        from src.reporting import generate_methods_text
    except ImportError:
        generate_methods_text = None

    if not generate_methods_text:
        return jsonify({"error": "Boilerplate generator not available"}), 500

    try:
        data = request.get_json()
        files = data.get("files", [])
        if not files:
            return jsonify({"error": "No files selected"}), 400

        file_paths = []
        for file_obj in files:
            if isinstance(file_obj, dict) and file_obj.get("path"):
                file_paths.append(file_obj.get("path"))
            elif isinstance(file_obj, str):
                file_paths.append(file_obj)

        valid_files = [file_path for file_path in file_paths if os.path.exists(file_path)]
        if not valid_files:
            return jsonify({"error": "No valid files found"}), 404

        fd, temp_path = tempfile.mkstemp(suffix=".md")
        os.close(fd)

        language = data.get("language", "en")
        github_url = "https://github.com/MRI-Lab-Graz/prism-studio"
        try:
            from src.schema_manager import DEFAULT_SCHEMA_VERSION

            schema_version = DEFAULT_SCHEMA_VERSION
        except ImportError:
            schema_version = "stable"

        generate_methods_text(
            valid_files,
            temp_path,
            lang=language,
            github_url=github_url,
            schema_version=schema_version,
        )

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
    import pandas as pd

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    filename = file.filename.lower()

    try:
        columns = []
        df = None

        if filename.endswith(".lsa"):
            import shutil

            tmp_dir = tempfile.mkdtemp(prefix="prism_detect_cols_")
            try:
                tmp_path = Path(tmp_dir) / filename
                file.save(str(tmp_path))
                from src.converters.limesurvey import parse_lsa_responses

                df, _, _ = parse_lsa_responses(str(tmp_path))
                columns = list(df.columns)
            except Exception as lsa_err:
                return jsonify({"error": f"Failed to read .lsa: {lsa_err}"}), 400
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        elif filename.endswith(".xlsx"):
            df = pd.read_excel(file)
            columns = list(df.columns)

        elif filename.endswith(".csv"):
            df = pd.read_csv(file)
            columns = list(df.columns)

        elif filename.endswith(".tsv"):
            df = pd.read_csv(file, sep="\t")
            columns = list(df.columns)

        else:
            return jsonify({"columns": [], "suggested_id_column": None})

        from src.converters.id_detection import detect_id_column, has_prismmeta_columns

        has_prismmeta = has_prismmeta_columns(columns)
        is_prism_data = has_prismmeta or any(
            c.lower()
            in (
                "participant_id",
                "participantid",
                "prism_participant_id",
                "prismparticipantid",
            )
            for c in columns
        )
        source_format = "lsa" if filename.endswith(".lsa") else "xlsx"
        suggested = detect_id_column(
            columns,
            source_format,
            has_prismmeta=has_prismmeta,
        )

        session_column = None
        detected_sessions = []
        if columns and df is not None:
            lower_to_col = {str(c).strip().lower(): str(c).strip() for c in columns}
            for candidate in ("session", "ses", "visit", "timepoint"):
                if candidate in lower_to_col:
                    session_column = lower_to_col[candidate]
                    break

            if session_column and session_column in df.columns:
                detected_sessions = sorted(
                    [
                        str(v).strip()
                        for v in df[session_column].dropna().unique()
                        if str(v).strip()
                    ]
                )

        return jsonify(
            {
                "columns": columns,
                "suggested_id_column": suggested,
                "is_prism_data": is_prism_data,
                "session_column": session_column,
                "detected_sessions": detected_sessions,
            }
        )

    except Exception as e:
        import traceback

        error_msg = str(e)
        print(f"ERROR in /api/detect-columns: {error_msg}")
        print(traceback.format_exc())
        return jsonify({"error": error_msg}), 500
