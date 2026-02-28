import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from flask import jsonify, send_file


def handle_survey_customizer_load(data, detect_languages_from_template):
    """Build survey customizer groups from selected template files."""
    files = data.get("files", [])
    display_language = data.get("language", "en")

    if not files:
        return jsonify({"error": "No files provided"}), 400

    groups = []

    for file_config in files:
        file_path = file_config.get("path")
        include_questions = file_config.get("includeQuestions", [])
        max_run_number = file_config.get("runNumber", 1)

        if not file_path or not os.path.exists(file_path):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as file_handle:
                template_data = json.load(file_handle)
        except Exception:
            continue

        study_info = template_data.get("Study", {})
        base_group_name = (
            study_info.get("OriginalName")
            or template_data.get("TaskName")
            or Path(file_path).stem
        )
        if isinstance(base_group_name, dict):
            base_group_name = (
                base_group_name.get(display_language)
                or base_group_name.get("en")
                or next(iter(base_group_name.values()), Path(file_path).stem)
            )

        technical = template_data.get("Technical", {})
        matrix_grouping_disabled = technical.get("MatrixGrouping") is False
        template_languages = detect_languages_from_template(template_data)

        if "Questions" in template_data and isinstance(template_data["Questions"], dict):
            all_questions = template_data["Questions"]
        else:
            reserved = [
                "@context",
                "Technical",
                "Study",
                "Metadata",
                "Categories",
                "TaskName",
                "I18n",
                "Scoring",
                "Normative",
            ]
            all_questions = {
                key: value
                for key, value in template_data.items()
                if key not in reserved
                and isinstance(value, dict)
                and "Description" in value
                and not value.get("_exclude", False)
            }

        if include_questions:
            filtered_questions = {
                key: value
                for key, value in all_questions.items()
                if key in include_questions
            }
        else:
            filtered_questions = all_questions

        for current_run in range(1, max_run_number + 1):
            questions = []
            for index, (question_code, question_data) in enumerate(
                filtered_questions.items()
            ):
                if not isinstance(question_data, dict):
                    question_data = {"Description": str(question_data)}

                description = question_data.get("Description", "")
                if isinstance(description, dict):
                    description = (
                        description.get(display_language)
                        or description.get("en")
                        or next(iter(description.values()), "")
                    )

                ls_props = question_data.get("LimeSurvey", {})
                tool_overrides = {}
                if ls_props:
                    if "questionType" in ls_props:
                        tool_overrides["questionType"] = ls_props["questionType"]
                    if "inputWidth" in ls_props:
                        tool_overrides["inputWidth"] = ls_props["inputWidth"]
                    if "displayRows" in ls_props:
                        tool_overrides["displayRows"] = ls_props["displayRows"]
                    if "Relevance" in ls_props:
                        tool_overrides["relevance"] = ls_props["Relevance"]
                    if "equation" in ls_props:
                        tool_overrides["equation"] = ls_props["equation"]
                    if "hidden" in ls_props:
                        tool_overrides["hidden"] = ls_props["hidden"]
                    if "validation" in ls_props:
                        validation = ls_props["validation"]
                        if isinstance(validation, dict):
                            if "min" in validation:
                                tool_overrides["validationMin"] = validation["min"]
                            if "max" in validation:
                                tool_overrides["validationMax"] = validation["max"]
                            if "integerOnly" in validation:
                                tool_overrides["integerOnly"] = validation[
                                    "integerOnly"
                                ]

                    simple_key_map = {
                        "cssclass": "cssClass",
                        "page_break": "pageBreak",
                        "maximum_chars": "maximumChars",
                        "numbers_only": "numbersOnly",
                        "display_columns": "displayColumns",
                        "alphasort": "alphasort",
                        "dropdown_size": "dropdownSize",
                        "dropdown_prefix": "dropdownPrefix",
                        "category_separator": "categorySeparator",
                        "answer_width": "answerWidth",
                        "repeat_headings": "repeatHeadings",
                        "use_dropdown": "useDropdown",
                        "input_size": "inputSize",
                        "prefix": "prefix",
                        "suffix": "suffix",
                        "placeholder": "placeholder",
                    }
                    for ls_key, override_key in simple_key_map.items():
                        if ls_key in ls_props:
                            tool_overrides[override_key] = ls_props[ls_key]

                questions.append(
                    {
                        "id": str(uuid.uuid4()),
                        "sourceFile": file_path,
                        "questionCode": question_code,
                        "description": description,
                        "displayOrder": index,
                        "mandatory": question_data.get("Mandatory", True),
                        "enabled": True,
                        "runNumber": current_run,
                        "levels": question_data.get("Levels", {}),
                        "originalData": question_data,
                        "matrixGroupingDisabled": matrix_grouping_disabled,
                        "toolOverrides": tool_overrides,
                        "inputType": question_data.get("InputType", ""),
                        "minValue": question_data.get("MinValue"),
                        "maxValue": question_data.get("MaxValue"),
                        "dataType": question_data.get("DataType", ""),
                        "help": question_data.get("Help", ""),
                    }
                )

            group_name = base_group_name
            if max_run_number > 1:
                group_name = f"{base_group_name} (Run {current_run})"

            groups.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": group_name,
                    "order": len(groups),
                    "sourceFile": file_path,
                    "runNumber": current_run,
                    "questions": questions,
                    "detected_languages": template_languages,
                    "instructions": study_info.get("Instructions", {}),
                }
            )

    if not groups:
        return jsonify({"error": "No valid questions found in selected files"}), 400

    return jsonify(
        {"groups": groups, "totalQuestions": sum(len(group["questions"]) for group in groups)}
    )


def handle_survey_customizer_export(data, project_path):
    """Export customized survey groups to LimeSurvey .lss file."""
    try:
        from src.limesurvey_exporter import generate_lss_from_customization
    except ImportError:
        return jsonify({"error": "LimeSurvey exporter not available"}), 500

    export_format = data.get("exportFormat", "limesurvey")
    if export_format != "limesurvey":
        return (
            jsonify({"error": f"Export format '{export_format}' not yet supported"}),
            400,
        )

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
    if save_to_project and project_path:
        lib_dir = Path(project_path) / "code" / "library" / "survey"
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

    try:
        fd, temp_path = tempfile.mkstemp(suffix=".lss")
        os.close(fd)

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

        safe_title = re.sub(r"[^\w\s-]", "", survey_title)
        safe_title = re.sub(r"[\s]+", "_", safe_title).strip("_")
        if not safe_title:
            safe_title = "survey"
        date_str = datetime.now().strftime("%Y-%m-%d")
        download_filename = f"{safe_title}_{date_str}.lss"

        response = send_file(
            temp_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype="application/xml",
        )
        if templates_saved:
            response.headers["X-Templates-Saved"] = str(templates_saved)
            response.headers["Access-Control-Expose-Headers"] = "X-Templates-Saved"
        return response
    except Exception as error:
        return jsonify({"error": str(error)}), 500


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
            }
        ]
    }