"""Survey Customizer backend: turn selected PRISM templates into editable
question groups (the structure `survey export-lss-customized` consumes).

Shared by the Studio Survey Customizer page and `prism_tools.py survey
customizer-groups`. Keep Flask out of this module.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from src.limesurvey_exporter import item_is_mandatory, ls_question_type
from src.survey_export_settings import strip_export_settings
from src.template_info import detect_languages_from_template


def build_customizer_groups(
    files: list[dict],
    display_language: str = "en",
    *,
    detect_languages=detect_languages_from_template,
) -> list[dict]:
    """Build customizer groups from ``files`` entries
    (``{"path", "includeQuestions", "runNumber"}``). Unreadable or missing
    files are skipped; returns an empty list when nothing usable was found."""
    groups: list = []

    for file_config in files:
        file_path = file_config.get("path")
        include_questions = file_config.get("includeQuestions", [])
        max_run_number = file_config.get("runNumber", 1)

        if not file_path or not os.path.exists(file_path):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as file_handle:
                # an old file may still carry export settings: load it like its stripped form
                template_data = strip_export_settings(json.load(file_handle))[0]
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
        template_languages = detect_languages(template_data)

        if "Questions" in template_data and isinstance(
            template_data["Questions"], dict
        ):
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
        # the template's own DisplayOrder decides (stable: items without one keep file order, last)
        filtered_questions = dict(sorted(
            filtered_questions.items(),
            key=lambda kv: kv[1].get("DisplayOrder", 999) if isinstance(kv[1], dict) else 999,
        ))

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

                questions.append(
                    {
                        "id": str(uuid.uuid4()),
                        "sourceFile": file_path,
                        "questionCode": question_code,
                        "description": description,
                        "displayOrder": index,
                        "mandatory": item_is_mandatory(question_data),
                        "enabled": True,
                        "runNumber": current_run,
                        "levels": question_data.get("Levels", {}),
                        "originalData": question_data,
                        "matrixGroupingDisabled": matrix_grouping_disabled,
                        "toolOverrides": {},  # the user's per-export changes; the template holds none
                        "questionType": ls_question_type(question_data),
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

    return groups
