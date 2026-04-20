import json
import re
from pathlib import Path

from flask import jsonify, request
from .projects_helpers import (
    _read_tabular_dataframe,
    _resolve_project_root_path,
    _resolve_requested_or_current_project_root,
)


def _normalize_schema_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _is_participant_id_field(field_name: str, field_schema: dict | None = None) -> bool:
    name_norm = _normalize_schema_key(field_name)
    if name_norm in {"participantid", "participantsid"}:
        return True

    if not isinstance(field_schema, dict):
        return False

    annotations = field_schema.get("Annotations")
    if not isinstance(annotations, dict):
        return False

    is_about = annotations.get("IsAbout")
    if not isinstance(is_about, dict):
        return False

    term_url = str(is_about.get("TermURL") or "").strip().lower()
    if term_url == "nb:participantid":
        return True

    label_norm = _normalize_schema_key(is_about.get("Label"))
    return label_norm in {"participantid", "subjectid"}


def _merge_participants_schema_field(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)

    for key, value in incoming.items():
        if key == "Annotations" and isinstance(value, dict):
            current_annotations = merged.get("Annotations")
            if not isinstance(current_annotations, dict):
                merged["Annotations"] = dict(value)
                continue

            next_annotations = dict(current_annotations)
            for ann_key, ann_value in value.items():
                if (
                    ann_key in next_annotations
                    and isinstance(next_annotations[ann_key], dict)
                    and isinstance(ann_value, dict)
                ):
                    combined = dict(next_annotations[ann_key])
                    combined.update(ann_value)
                    next_annotations[ann_key] = combined
                elif ann_key not in next_annotations:
                    next_annotations[ann_key] = ann_value

            merged["Annotations"] = next_annotations
            continue

        current_value = merged.get(key)
        is_empty_struct = current_value == {} or current_value == []
        if (
            key not in merged
            or current_value is None
            or current_value == ""
            or is_empty_struct
        ):
            merged[key] = value

    return merged


def _canonicalize_participant_schema_keys(schema: dict) -> dict:
    if not isinstance(schema, dict):
        return {}

    canonical: dict = {}

    # Process canonical participant_id-like keys first so their values take precedence
    # when alias/source keys (e.g., Code with nb:ParticipantID) are merged.
    items = list(schema.items())
    items.sort(
        key=lambda item: (
            0
            if _normalize_schema_key(item[0]) in {"participantid", "participantsid"}
            else 1
        )
    )

    for raw_key, raw_field in items:
        key = str(raw_key or "").strip()
        if not key:
            continue

        field = dict(raw_field) if isinstance(raw_field, dict) else raw_field
        target_key = (
            "participant_id"
            if _is_participant_id_field(
                key, raw_field if isinstance(raw_field, dict) else None
            )
            else key
        )

        if target_key not in canonical:
            canonical[target_key] = field
            continue

        existing = canonical[target_key]
        if isinstance(existing, dict) and isinstance(field, dict):
            canonical[target_key] = _merge_participants_schema_field(existing, field)

    return canonical


def _resolve_current_project_root(current_project: dict) -> Path | None:
    """Resolve current project path to dataset root (accept dir or project.json path)."""
    return _resolve_project_root_path(str(current_project.get("path") or ""))


def handle_get_participants_schema(get_current_project, get_bids_file_path):
    """Get the participants.json schema for the current project."""
    project_path, error_message, status_code = _resolve_requested_or_current_project_root(
        get_current_project,
        request.args.get("project_path"),
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    current = get_current_project()

    participants_path = get_bids_file_path(project_path, "participants.json")

    if not participants_path.exists():
        return jsonify(
            {
                "success": True,
                "exists": False,
                "schema": {},
                "project_path": str(project_path),
                "project_name": current.get("name"),
            }
        )

    try:
        with open(participants_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        return jsonify(
            {
                "success": True,
                "exists": True,
                "schema": schema,
                "fields": list(schema.keys()),
                "project_path": str(project_path),
                "project_name": current.get("name"),
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to read participants.json: {str(e)}",
                }
            ),
            500,
        )


def handle_save_participants_schema(get_current_project, get_bids_file_path):
    """Save the participants.json schema for the current project."""
    data = request.get_json()
    if not data or "schema" not in data:
        return jsonify({"success": False, "error": "No schema provided"}), 400

    project_path, error_message, status_code = _resolve_requested_or_current_project_root(
        get_current_project,
        data.get("project_path"),
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    schema = data["schema"]
    if not isinstance(schema, dict):
        return jsonify({"success": False, "error": "Schema must be a dictionary"}), 400

    schema = _canonicalize_participant_schema_keys(schema)

    if "participant_id" not in schema:
        schema = {
            "participant_id": {"Description": "Unique participant identifier"},
            **schema,
        }
    elif isinstance(schema.get("participant_id"), dict):
        description = str(schema["participant_id"].get("Description") or "").strip()
        if not description:
            schema["participant_id"]["Description"] = "Unique participant identifier"

    participants_path = get_bids_file_path(project_path, "participants.json")

    try:
        with open(participants_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

        rewrite_summary = {
            "enabled": False,
            "file_found": False,
            "columns_touched": 0,
            "replacements": 0,
            "details": {},
        }

        return jsonify(
            {
                "success": True,
                "message": "participants.json saved successfully",
                "fields": list(schema.keys()),
                "schema": schema,
                "path": str(participants_path),
                "value_rewrite_summary": rewrite_summary,
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to save participants.json: {str(e)}",
                }
            ),
            500,
        )


def handle_get_participants_columns(get_current_project, get_bids_file_path):
    """Extract unique values from project's participants.tsv."""
    project_path, error_message, status_code = _resolve_requested_or_current_project_root(
        get_current_project,
        request.args.get("project_path"),
    )
    if project_path is None:
        return jsonify({"error": error_message}), status_code

    tsv_path = get_bids_file_path(project_path, "participants.tsv")

    if not tsv_path.exists():
        return jsonify({"columns": {}})

    try:
        df = _read_tabular_dataframe(tsv_path, expected_delimiter="\t")
        result = {}
        for col in df.columns:
            if col.lower() not in ["participant_id", "id"] and df[col].nunique() < 50:
                unique_vals = [str(v) for v in df[col].dropna().unique().tolist()]
                result[col] = sorted(unique_vals)
            else:
                result[col] = []

        return jsonify({"columns": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_get_participants_templates():
    """Get predefined BIDS-compatible field templates."""
    templates = {
        "required": {
            "participant_id": {
                "Description": "Unique participant identifier",
                "_help": "REQUIRED by BIDS. Format: sub-<label> (e.g., sub-001)",
                "_required": True,
            }
        },
        "demographics": {
            "age": {
                "Description": "Age of participant",
                "Unit": "years",
                "_help": "Recommended. Can be exact age or age range for anonymity.",
            },
            "sex": {
                "Description": "Biological sex",
                "Levels": {
                    "M": "Male",
                    "F": "Female",
                    "O": "Other",
                    "DNS": "Did not say",
                },
                "_help": "BIDS recommended. Biological sex assigned at birth.",
            },
            "gender": {
                "Description": "Gender identity",
                "Levels": {
                    "woman": "Woman",
                    "man": "Man",
                    "non_binary": "Non-binary",
                    "other": "Other",
                    "DNS": "Did not say",
                },
                "_help": "Self-identified gender. Separate from biological sex.",
            },
            "handedness": {
                "Description": "Handedness",
                "Levels": {"R": "Right", "L": "Left", "A": "Ambidextrous"},
                "_help": "BIDS recommended for neuroimaging studies.",
            },
        },
        "education": {
            "education_level": {
                "Description": "Highest completed education level",
                "Levels": {
                    "1": "Primary education",
                    "2": "Secondary education",
                    "3": "Vocational training",
                    "4": "Bachelor's degree",
                    "5": "Master's degree",
                    "6": "Doctorate",
                    "7": "Other",
                },
                "_help": "Categorical education level.",
            },
            "education_years": {
                "Description": "Years of formal education completed",
                "Unit": "years",
                "_help": "Continuous measure of education.",
            },
        },
        "socioeconomic": {
            "employment_status": {
                "Description": "Employment status",
                "Levels": {
                    "employed": "Employed",
                    "self_employed": "Self-employed",
                    "unemployed": "Unemployed",
                    "student": "Student",
                    "retired": "Retired",
                    "other": "Other",
                },
            },
            "marital_status": {
                "Description": "Marital status",
                "Levels": {
                    "single": "Single",
                    "partnered": "Partnered",
                    "married": "Married",
                    "divorced": "Divorced",
                    "widowed": "Widowed",
                },
            },
            "household_size": {
                "Description": "Number of people in the household",
                "Unit": "persons",
            },
        },
        "geographic": {
            "country_of_residence": {
                "Description": "Country of residence",
                "_help": "Use ISO 3166-1 alpha-2 codes (e.g., AT, DE, US).",
            },
            "native_language": {
                "Description": "Native language",
                "_help": "Use ISO 639-1 codes (e.g., de, en, fr).",
            },
        },
        "health": {
            "height": {"Description": "Body height", "Unit": "cm"},
            "weight": {"Description": "Body weight", "Unit": "kg"},
            "bmi": {"Description": "Body mass index", "Unit": "kg/m^2"},
            "smoking_status": {
                "Description": "Smoking status",
                "Levels": {
                    "never": "Never smoked",
                    "former": "Former smoker",
                    "current": "Current smoker",
                },
            },
            "vision": {
                "Description": "Vision status",
                "Levels": {
                    "normal": "Normal/corrected to normal",
                    "impaired": "Impaired",
                },
                "_help": "Important for visual experiments.",
            },
            "hearing": {
                "Description": "Hearing status",
                "Levels": {"normal": "Normal", "impaired": "Impaired"},
                "_help": "Important for auditory experiments.",
            },
        },
        "study": {
            "group": {
                "Description": "Study group assignment",
                "Levels": {
                    "control": "Control group",
                    "experimental": "Experimental group",
                },
                "_help": "Define your study-specific groups.",
            },
            "session_date": {
                "Description": "Date of data collection",
                "Unit": "ISO 8601 date",
                "_help": "Format: YYYY-MM-DD",
            },
        },
    }

    tips = [
        {
            "level": "required",
            "message": "participant_id is REQUIRED by BIDS specification",
            "field": "participant_id",
        },
        {
            "level": "recommended",
            "message": "BIDS recommends including age, sex, and handedness for all datasets",
            "fields": ["age", "sex", "handedness"],
        },
        {
            "level": "info",
            "message": "Use standard units (years, cm, kg) and ISO codes for countries/languages",
            "fields": [],
        },
        {
            "level": "info",
            "message": "Each field should have a Description. Use Levels for categorical data and Units for continuous data.",
            "fields": [],
        },
        {
            "level": "privacy",
            "message": "Consider anonymization: use age ranges instead of exact ages, avoid identifying information",
            "fields": ["age", "country_of_residence"],
        },
    ]

    return jsonify(
        {
            "success": True,
            "templates": templates,
            "tips": tips,
            "categories": list(templates.keys()),
        }
    )
