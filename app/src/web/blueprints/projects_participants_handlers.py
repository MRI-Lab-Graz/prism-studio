import json
from pathlib import Path

from flask import jsonify, request


def handle_get_participants_schema(get_current_project, get_bids_file_path):
    """Get the participants.json schema for the current project."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
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
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    data = request.get_json()
    if not data or "schema" not in data:
        return jsonify({"success": False, "error": "No schema provided"}), 400

    schema = data["schema"]
    if not isinstance(schema, dict):
        return jsonify({"success": False, "error": "Schema must be a dictionary"}), 400

    if "participant_id" not in schema:
        schema = {
            "participant_id": {"Description": "Unique participant identifier"},
            **schema,
        }

    project_path = Path(current["path"])
    participants_path = get_bids_file_path(project_path, "participants.json")

    try:
        with open(participants_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

        return jsonify(
            {
                "success": True,
                "message": "participants.json saved successfully",
                "fields": list(schema.keys()),
                "path": str(participants_path),
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
    import pandas as pd

    current = get_current_project()
    if not current.get("path"):
        return jsonify({"error": "No project selected"}), 400

    project_path = Path(current["path"])
    tsv_path = get_bids_file_path(project_path, "participants.tsv")

    if not tsv_path.exists():
        return jsonify({"columns": {}})

    try:
        df = pd.read_csv(tsv_path, sep="\t")
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