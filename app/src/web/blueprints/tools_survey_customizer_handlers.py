import io
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from flask import jsonify, send_file

from src.survey_customizer import build_customizer_groups

from .conversion_utils import require_existing_project_root


def handle_survey_customizer_load(data, detect_languages_from_template):
    """Build survey customizer groups from selected template files."""
    files = data.get("files", [])
    display_language = data.get("language", "en")

    if not files:
        return jsonify({"error": "No files provided"}), 400

    groups = build_customizer_groups(
        files,
        display_language,
        detect_languages=detect_languages_from_template,
    )

    if not groups:
        return jsonify({"error": "No valid questions found in selected files"}), 400

    return jsonify(
        {
            "groups": groups,
            "totalQuestions": sum(len(group["questions"]) for group in groups),
        }
    )


def handle_survey_customizer_export(data, project_path):
    """Export customized survey groups to LimeSurvey (.lss) or Pavlovia/PsychoPy (.zip)."""
    export_format = data.get("exportFormat", "limesurvey")
    if export_format not in ("limesurvey", "pavlovia"):
        return (
            jsonify({"error": f"Export format '{export_format}' not yet supported"}),
            400,
        )

    if export_format == "limesurvey":
        try:
            from src.limesurvey_exporter import generate_lss_from_customization
        except ImportError:
            return jsonify({"error": "LimeSurvey exporter not available"}), 500
    else:
        try:
            from src.converters.pavlovia import generate_pavlovia_from_customization
        except ImportError:
            return jsonify({"error": "Pavlovia exporter not available"}), 500

    survey_info = data.get("survey", {})
    groups = data.get("groups", [])
    export_options = data.get("exportOptions", {})
    save_to_project = data.get("saveToProject", False)

    if not groups:
        return jsonify({"error": "No groups to export"}), 400

    survey_title = survey_info.get("title", "").strip()
    if not survey_title:
        return jsonify({"error": "Survey name is required"}), 400

    language = survey_info.get("language", "en")
    languages = survey_info.get("languages") or data.get("languages") or [language]
    base_language = (
        survey_info.get("base_language") or data.get("base_language") or language
    )
    ls_version = export_options.get("ls_version", "3")
    matrix_mode = export_options.get("matrix", True)
    matrix_global = export_options.get("matrix_global", True)
    ls_settings = data.get("lsSettings") or {}

    templates_saved = 0
    if save_to_project:
        try:
            project_root = require_existing_project_root(
                project_path,
                missing_message="No active project selected. Open a project before saving templates.",
                missing_path_message="The selected project path no longer exists. Reopen the project and retry the export.",
            )
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 400

        lib_dir = project_root / "code" / "library" / "survey"
        try:
            lib_dir.mkdir(parents=True, exist_ok=True)
            seen = set()
            for group in groups:
                source_path = group.get("sourceFile") or ""
                if not source_path or source_path in seen:
                    continue
                seen.add(source_path)

                src_path = Path(source_path)
                if not src_path.is_file():
                    continue

                dest = lib_dir / src_path.name
                try:
                    dest.resolve().relative_to(lib_dir.resolve())
                    if src_path.resolve() == dest.resolve():
                        continue
                except ValueError:
                    pass

                shutil.copy2(str(src_path), str(dest))
                templates_saved += 1
        except OSError:
            pass

    safe_title = re.sub(r"[^\w\s-]", "", survey_title)
    safe_title = re.sub(r"[\s]+", "_", safe_title).strip("_")
    if not safe_title:
        safe_title = "survey"
    date_str = datetime.now().strftime("%Y-%m-%d")

    if export_format == "limesurvey":
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".lss")
            os.close(fd)

            try:
                generate_lss_from_customization(
                    groups=groups,
                    output_path=temp_path,
                    language=language,
                    languages=languages,
                    base_language=base_language,
                    ls_version=ls_version,
                    matrix_mode=matrix_mode,
                    matrix_global=matrix_global,
                    survey_title=survey_title,
                    ls_settings=ls_settings,
                )
                lss_bytes = Path(temp_path).read_bytes()
            finally:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

            response = send_file(
                io.BytesIO(lss_bytes),
                as_attachment=True,
                download_name=f"{safe_title}_{date_str}.lss",
                mimetype="application/xml",
            )
        except Exception as error:
            return jsonify({"error": str(error)}), 500
    else:
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                output_dir = Path(tmp_dir) / "export"
                generate_pavlovia_from_customization(
                    groups=groups,
                    output_dir=output_dir,
                    experiment_name=safe_title,
                    language=base_language,
                )

                zip_fd, zip_path = tempfile.mkstemp(suffix=".zip")
                os.close(zip_fd)
                try:
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for file_path in output_dir.rglob("*"):
                            if file_path.is_file():
                                zf.write(file_path, file_path.relative_to(output_dir))
                    zip_bytes = Path(zip_path).read_bytes()
                finally:
                    try:
                        os.remove(zip_path)
                    except OSError:
                        pass

            response = send_file(
                io.BytesIO(zip_bytes),
                as_attachment=True,
                download_name=f"{safe_title}_{date_str}.zip",
                mimetype="application/zip",
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except Exception as error:
            return jsonify({"error": str(error)}), 500

    if templates_saved:
        response.headers["X-Templates-Saved"] = str(templates_saved)
        response.headers["Access-Control-Expose-Headers"] = "X-Templates-Saved"
    return response


def get_survey_customizer_formats_payload():
    """List available export formats for the survey customizer."""
    return {
        "formats": [
            {
                "id": "limesurvey",
                "name": "LimeSurvey",
                "extension": ".lss",
                "description": "LimeSurvey Survey Structure file",
                "options": [
                    {
                        "id": "ls_version",
                        "name": "LimeSurvey Version",
                        "type": "select",
                        "default": "6",
                        "choices": [
                            {
                                "value": "6",
                                "label": "LimeSurvey 5.x / 6.x (Modern)",
                            },
                            {"value": "3", "label": "LimeSurvey 3.x (Legacy)"},
                        ],
                    },
                    {
                        "id": "matrix",
                        "name": "Group as matrices",
                        "type": "boolean",
                        "default": True,
                    },
                    {
                        "id": "matrix_global",
                        "name": "Global matrix grouping",
                        "type": "boolean",
                        "default": True,
                    },
                ],
            },
            {
                "id": "pavlovia",
                "name": "Pavlovia/PsychoPy",
                "extension": ".zip",
                "description": "PsychoPy Builder experiment packaged with a conditions spreadsheet and README",
                "options": [],
            },
        ],
    }
