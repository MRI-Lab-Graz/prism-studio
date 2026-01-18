import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

# Ensure project root is available for relative imports when this module runs standalone
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from ..utils.naming import sanitize_task_name
except (ImportError, ValueError):
    try:
        from utils.naming import sanitize_task_name
    except (ImportError, ValueError):
        sanitize_task_name = lambda x: x


def _apply_survey_metadata(metadata: Dict[str, Dict[str, object]], survey_meta: Dict[str, object]) -> None:
    study = metadata.get("Study", {})
    technical = metadata.get("Technical", {})

    if survey_meta.get("admin"):
        study["Author"] = survey_meta["admin"]
    if survey_meta.get("admin_email"):
        study["ContactEmail"] = survey_meta["admin_email"]
    if survey_meta.get("anonymized"):
        technical["Anonymized"] = survey_meta["anonymized"]
    if survey_meta.get("template"):
        technical["Template"] = survey_meta["template"]


def _build_question_entry(q_data: Dict[str, object], group_name: str, group_order: int) -> Dict[str, object]:
    entry: Dict[str, object] = {
        "Description": q_data["question"],
        "QuestionType": q_data["type_name"],
        "Mandatory": q_data["mandatory"],
        "Position": {
            "Group": group_name,
            "GroupOrder": group_order,
            "QuestionOrder": q_data["question_order"],
        },
    }

    if q_data.get("levels"):
        entry["Levels"] = q_data["levels"]

    if q_data.get("subquestions"):
        items: Dict[str, Dict[str, object]] = {}
        for sq in q_data["subquestions"]:
            item_entry = {
                "Description": sq["text"],
                "Order": sq["order"],
            }
            if sq["scale_id"] != 0:
                item_entry["ScaleId"] = sq["scale_id"]
            if sq.get("media_urls"):
                item_entry["MediaUrls"] = sq["media_urls"]
            items[sq["code"]] = item_entry
        entry["Items"] = items

    if q_data.get("other"):
        entry["HasOtherOption"] = True
    if q_data.get("help"):
        entry["HelpText"] = q_data["help"]
    if q_data.get("validation_regex"):
        entry["ValidationRegex"] = q_data["validation_regex"]
    if q_data.get("relevance"):
        entry["Condition"] = q_data["relevance"]

    if q_data.get("attributes"):
        attrs = {k: v for k, v in q_data["attributes"].items() if v not in (None, "", 0)}
        if attrs:
            entry["Attributes"] = attrs

    return entry


def build_prism_for_survey(
    questions_map: Dict[str, Dict[str, object]],
    groups_map: Dict[str, Dict[str, object]],
    survey_meta: Dict[str, object],
    task_name: str | None = None,
) -> Dict[str, object]:
    prism_json: Dict[str, Dict[str, object]] = {}
    sorted_questions = sorted(
        questions_map.items(),
        key=lambda x: (
            groups_map.get(x[1]["gid"], {}).get("order", 0),
            x[1]["question_order"],
        ),
    )

    for _, q_data in sorted_questions:
        key = q_data["title"]
        group_info = groups_map.get(q_data["gid"], {"name": "", "order": 0})
        entry = _build_question_entry(q_data, group_info.get("name", ""), group_info.get("order", 0))
        prism_json[key] = entry

    survey_title = survey_meta.get("title") or task_name or "survey"
    normalized_task = sanitize_task_name(survey_title)
    description = survey_meta.get("description") or f"Imported from LimeSurvey: {survey_title}"

    metadata = {
        "Technical": {
            "StimulusType": "Questionnaire",
            "FileFormat": "tsv",
            "SoftwarePlatform": "LimeSurvey",
            "Language": survey_meta.get("language", "en"),
            "Respondent": "self",
            "ResponseType": ["online"],
        },
        "Study": {
            "TaskName": normalized_task,
            "OriginalName": survey_title,
            "Version": "1.0",
            "Description": description,
            "ItemCount": len(prism_json),
            "LicenseID": "Proprietary",
            "License": "Proprietary / Copyright protected. Please ensure you have a valid license for this instrument.",
        },
        "Metadata": {
            "SchemaVersion": "1.1.1",
            "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "Creator": "limesurvey_to_prism.py",
        },
    }

    _apply_survey_metadata(metadata, survey_meta)
    metadata.update(prism_json)
    return metadata


def build_prism_by_groups(
    questions_map: Dict[str, Dict[str, object]],
    groups_map: Dict[str, Dict[str, object]],
    survey_meta: Dict[str, object],
) -> Dict[str, Dict[str, object]]:
    grouped_questions: Dict[str, list[tuple[str, Dict[str, object]]]] = {}
    for qid, q_data in questions_map.items():
        gid = q_data.get("gid", "")
        grouped_questions.setdefault(gid, []).append((qid, q_data))

    sorted_groups = sorted(grouped_questions.items(), key=lambda x: groups_map.get(x[0], {}).get("order", 0))
    result: Dict[str, Dict[str, object]] = {}

    for gid, questions_list in sorted_groups:
        if not questions_list:
            continue

        group_info = groups_map.get(gid, {"name": f"group_{gid}", "order": 0, "description": ""})
        group_name = group_info.get("name") or f"group_{gid}"
        group_order = group_info.get("order", 0)
        group_description = group_info.get("description", "")

        sorted_questions = sorted(questions_list, key=lambda x: x[1]["question_order"])
        questions_dict: Dict[str, Dict[str, object]] = {}
        for _, q_data in sorted_questions:
            key = q_data["title"]
            entry = _build_question_entry(q_data, group_name, group_order)
            questions_dict[key] = entry

        normalized_name = sanitize_task_name(group_name)
        study_description = group_description if group_description else f"Imported from LimeSurvey group: {group_name}"

        prism_json = {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv",
                "SoftwarePlatform": "LimeSurvey",
                "Language": survey_meta.get("language", "en"),
                "Respondent": "self",
                "ResponseType": ["online"],
            },
            "Study": {
                "TaskName": normalized_name,
                "OriginalName": group_name,
                "SurveyTitle": survey_meta.get("title", ""),
                "Version": "1.0",
                "Description": study_description,
                "GroupOrder": group_order,
                "ItemCount": len(questions_dict),
                "LicenseID": "Proprietary",
                "License": "Proprietary / Copyright protected. Please ensure you have a valid license for this instrument.",
            },
            "Metadata": {
                "SchemaVersion": "1.1.1",
                "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
                "Creator": "limesurvey_to_prism.py",
            },
        }

        _apply_survey_metadata(prism_json, survey_meta)
        prism_json.update(questions_dict)
        result[normalized_name] = prism_json

    return result


def build_prism_question_templates(
    questions_map: Dict[str, Dict[str, object]],
    groups_map: Dict[str, Dict[str, object]],
    survey_meta: Dict[str, object],
) -> Dict[str, Dict[str, object]]:
    result: Dict[str, Dict[str, object]] = {}

    for qid, q_data in questions_map.items():
        if q_data.get("parent_qid") and q_data["parent_qid"] != "0":
            continue

        question_code = q_data["title"]
        group_info = groups_map.get(q_data["gid"], {"name": f"group_{q_data['gid']}", "order": 0})
        group_name = group_info.get("name") or f"group_{q_data['gid']}"
        group_order = group_info.get("order", 0)

        entry = _build_question_entry(q_data, group_name, group_order)
        entry["LimeSurveyType"] = q_data["type"]

        if q_data.get("levels"):
            levels = {k: v for k, v in q_data["levels"].items() if v != ""}
            if levels:
                entry["Levels"] = levels

        question_json = {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv",
                "SoftwarePlatform": "LimeSurvey",
                "Language": survey_meta.get("language", "en"),
                "Respondent": "self",
                "ResponseType": ["online"],
            },
            "Study": {
                "TaskName": sanitize_task_name(question_code),
                "OriginalName": question_code,
                "QuestionCode": question_code,
                "GroupName": group_name,
                "GroupOrder": group_order,
                "Version": "1.0",
                "Description": q_data["question"][:200] if q_data["question"] else "",
                "LicenseID": "Proprietary",
                "License": "Proprietary / Copyright protected. Please ensure you have a valid license for this instrument.",
            },
            "Metadata": {
                "SchemaVersion": "1.1.1",
                "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
                "Creator": "limesurvey_to_prism.py",
                "SourceSurvey": survey_meta.get("title", ""),
            },
            question_code: entry,
        }

        _apply_survey_metadata(question_json, survey_meta)
        item_count = len(entry.get("Items", {})) if entry.get("Items") else 1
        question_json["Study"]["ItemCount"] = item_count

        result[question_code] = {
            "prism_json": question_json,
            "question_code": question_code,
            "question_type": q_data["type_name"],
            "limesurvey_type": q_data["type"],
            "group_name": group_name,
            "group_order": group_order,
            "question_order": q_data["question_order"],
            "item_count": item_count,
            "mandatory": q_data["mandatory"],
            "suggested_filename": f"survey-{sanitize_task_name(question_code)}.json",
        }

    return result