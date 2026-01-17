"""
Flask blueprint for project management functionality.

Provides routes for:
- Creating new PRISM projects
- Validating existing project structures
- Applying fixes to repair issues
- Managing current working project
"""

import os
from pathlib import Path
from flask import Blueprint, render_template, jsonify, request, session

from src.project_manager import ProjectManager, get_available_modalities

projects_bp = Blueprint("projects", __name__)

# Shared project manager instance
_project_manager = ProjectManager()


def get_current_project() -> dict:
    """Get the current working project from session."""
    return {
        "path": session.get("current_project_path"),
        "name": session.get("current_project_name")
    }


def set_current_project(path: str, name: str = None):
    """Set the current working project in session."""
    session["current_project_path"] = path
    session["current_project_name"] = name or Path(path).name


@projects_bp.route("/projects")
def projects_page():
    """Render the Projects management page."""
    current = get_current_project()
    return render_template(
        "projects.html",
        modalities=get_available_modalities(),
        current_project=current
    )


@projects_bp.route("/api/projects/current", methods=["GET"])
def get_current():
    """Get the current working project."""
    return jsonify(get_current_project())


@projects_bp.route("/api/projects/current", methods=["POST"])
def set_current():
    """Set or clear the current working project."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    path = data.get("path")

    # Allow clearing the current project by passing null/empty path
    if not path:
        session.pop("current_project_path", None)
        session.pop("current_project_name", None)
        return jsonify({"success": True, "current": get_current_project()})

    name = data.get("name")

    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Path does not exist"}), 400

    set_current_project(path, name)
    return jsonify({"success": True, "current": get_current_project()})


@projects_bp.route("/api/projects/create", methods=["POST"])
def create_project():
    """
    Create a new PRISM project (YODA layout).

    Expected JSON body:
    {
        "path": "/path/to/project",
        "name": "My Study"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        # Build config from request
        config = {
            "name": data.get("name", Path(path).name),
            # Optional BIDS metadata
            "authors": data.get("authors"),
            "license": data.get("license"),
            "doi": data.get("doi"),
            "keywords": data.get("keywords"),
            "acknowledgements": data.get("acknowledgements"),
            "ethics_approvals": data.get("ethics_approvals"),
            "how_to_acknowledge": data.get("how_to_acknowledge"),
            "funding": data.get("funding"),
            "references_and_links": data.get("references_and_links"),
            "hed_version": data.get("hed_version"),
            "dataset_type": data.get("dataset_type"),
            "description": data.get("description")
        }

        result = _project_manager.create_project(path, config)

        if result.get("success"):
            # Set as current working project
            set_current_project(path, config.get("name"))
            result["current_project"] = get_current_project()
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/validate", methods=["POST"])
def validate_project():
    """
    Validate an existing project structure.

    Expected JSON body:
    {
        "path": "/path/to/project"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        # Check if path exists
        if not os.path.exists(path):
            return jsonify({
                "success": False,
                "error": f"Path does not exist: {path}"
            }), 400

        result = _project_manager.validate_structure(path)
        result["success"] = True

        # Set as current working project
        set_current_project(path)
        result["current_project"] = get_current_project()

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/fix", methods=["POST"])
def fix_project():
    """
    Apply fixes to a project.

    Expected JSON body:
    {
        "path": "/path/to/project",
        "fix_codes": ["PRISM001", "PRISM501"]  // optional, null = fix all
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        fix_codes = data.get("fix_codes")  # None means fix all

        result = _project_manager.apply_fixes(path, fix_codes)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/fixable", methods=["POST"])
def get_fixable_issues():
    """
    Get list of fixable issues for a project.

    Expected JSON body:
    {
        "path": "/path/to/project"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        issues = _project_manager.get_fixable_issues(path)
        return jsonify({
            "success": True,
            "issues": issues
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/modalities", methods=["GET"])
def get_modalities():
    """Get list of available PRISM modalities."""
    return jsonify({
        "success": True,
        "modalities": get_available_modalities()
    })


@projects_bp.route("/api/settings/global-library", methods=["GET"])
def get_global_library_settings():
    """Get the global template library settings."""
    from src.config import load_app_settings
    from flask import current_app

    settings = load_app_settings()

    # Default library path is the app's survey_library folder
    app_root = Path(current_app.root_path)
    default_library_path = str(app_root / "survey_library")

    return jsonify({
        "success": True,
        "global_template_library_path": settings.global_template_library_path,
        "default_library_path": default_library_path,
        "default_modalities": settings.default_modalities,
    })


@projects_bp.route("/api/settings/global-library", methods=["POST"])
def set_global_library_settings():
    """Update the global template library settings."""
    from src.config import load_app_settings, save_app_settings
    from flask import current_app

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    # Load current settings
    settings = load_app_settings()

    # Update settings
    if "global_template_library_path" in data:
        path = data["global_template_library_path"]
        # Allow empty/null to clear the setting
        if path and path.strip():
            # Validate path exists
            if not os.path.exists(path):
                return jsonify({
                    "success": False,
                    "error": f"Path does not exist: {path}"
                }), 400
            settings.global_template_library_path = path
        else:
            settings.global_template_library_path = None

    if "default_modalities" in data:
        settings.default_modalities = data["default_modalities"]

    # Save settings to app root
    try:
        app_root = Path(current_app.root_path)
        settings_path = save_app_settings(settings, str(app_root))
        return jsonify({
            "success": True,
            "message": f"Settings saved to {settings_path}",
            "global_template_library_path": settings.global_template_library_path,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route("/api/projects/library-path", methods=["GET"])
def get_library_path():
    """Get the library paths for the current project.

    Returns information about both:
    - Global template library (shared, read-only from Nextcloud/GitLab)
    - Project library folder (user's own templates)

    Returns:
        JSON with library paths, project info, and structure flags
    """
    from src.config import get_effective_template_library_path, load_app_settings
    from flask import current_app

    current = get_current_project()
    app_settings = load_app_settings()

    # Default library path is the app's survey_library folder
    app_root = Path(current_app.root_path)
    default_library_path = str(app_root / "survey_library")

    # Use configured global path or default to survey_library
    effective_global_path = app_settings.global_template_library_path or default_library_path

    if not current.get("path"):
        # No project selected - still return global library
        return jsonify({
            "success": False,
            "message": "No project selected",
            "project_library_path": None,
            "project_library_exists": False,
            "global_library_path": effective_global_path,
            "library_path": effective_global_path,  # Legacy compatibility
        })

    project_path = Path(current["path"])

    # Get effective library paths
    library_info = get_effective_template_library_path(
        str(project_path),
        app_settings,
        app_root=str(app_root)
    )

    # Project's own library folder (YODA layout)
    project_library = project_path / "library"
    legacy_library = project_path / "code" / "library"

    # For legacy compatibility, provide a single "library_path" that works for conversion
    # Prefer project library if it exists, otherwise use external library
    legacy_library_path = None
    if project_library.exists():
        legacy_library_path = str(project_library)
    elif legacy_library.exists():
        legacy_library_path = str(legacy_library)
    elif library_info.get("effective_external_path"):
        legacy_library_path = library_info["effective_external_path"]
    else:
        legacy_library_path = str(project_path)

    return jsonify({
        "success": True,
        "project_path": str(project_path),
        "project_name": current.get("name"),

        # Dual library system
        "project_library_path": str(project_library),
        "project_library_exists": project_library.exists(),
        "global_library_path": library_info.get("global_library_path") or effective_global_path,
        "effective_external_path": library_info.get("effective_external_path"),
        "external_source": library_info.get("source"),  # 'project', 'global', or 'default'

        # Legacy compatibility
        "library_path": legacy_library_path,

        # Structure info
        "structure": {
            "has_project_library": project_library.exists() or legacy_library.exists(),
            "has_survey": (project_library / "survey").exists() if project_library.exists() else (legacy_library / "survey").exists(),
            "has_biometrics": (project_library / "biometrics").exists() if project_library.exists() else (legacy_library / "biometrics").exists(),
            "has_participants": (project_path / "rawdata" / "participants.json").exists(),
            "has_external_library": library_info.get("effective_external_path") is not None,
        }
    })


@projects_bp.route("/api/projects/participants", methods=["GET"])
def get_participants_schema():
    """Get the participants.json schema for the current project.

    Returns the current participants.json content and structure info.
    """
    import json

    current = get_current_project()
    if not current.get("path"):
        return jsonify({
            "success": False,
            "error": "No project selected"
        }), 400

    project_path = Path(current["path"])
    participants_path = project_path / "rawdata" / "participants.json"

    if not participants_path.exists():
        return jsonify({
            "success": True,
            "exists": False,
            "schema": {},
            "project_path": str(project_path),
            "project_name": current.get("name")
        })

    try:
        with open(participants_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        return jsonify({
            "success": True,
            "exists": True,
            "schema": schema,
            "fields": list(schema.keys()),
            "project_path": str(project_path),
            "project_name": current.get("name")
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to read participants.json: {str(e)}"
        }), 500


@projects_bp.route("/api/projects/participants", methods=["POST"])
def save_participants_schema():
    """Save the participants.json schema for the current project.

    Expected JSON body:
    {
        "schema": {
            "participant_id": {"Description": "..."},
            "age": {"Description": "...", "Units": "years"},
            ...
        }
    }
    """
    import json

    current = get_current_project()
    if not current.get("path"):
        return jsonify({
            "success": False,
            "error": "No project selected"
        }), 400

    data = request.get_json()
    if not data or "schema" not in data:
        return jsonify({
            "success": False,
            "error": "No schema provided"
        }), 400

    schema = data["schema"]

    # Validate schema structure
    if not isinstance(schema, dict):
        return jsonify({
            "success": False,
            "error": "Schema must be a dictionary"
        }), 400

    # Ensure participant_id is always included (BIDS requirement)
    if "participant_id" not in schema:
        schema = {"participant_id": {"Description": "Unique participant identifier"}, **schema}

    project_path = Path(current["path"])
    participants_path = project_path / "rawdata" / "participants.json"

    try:
        with open(participants_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

        return jsonify({
            "success": True,
            "message": "participants.json saved successfully",
            "fields": list(schema.keys()),
            "path": str(participants_path)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to save participants.json: {str(e)}"
        }), 500


@projects_bp.route("/api/projects/description", methods=["GET"])
def get_dataset_description():
    """Get the dataset_description.json for the current project."""
    import json

    current = get_current_project()
    if not current.get("path"):
        return jsonify({
            "success": False,
            "error": "No project selected"
        }), 400

    project_path = Path(current["path"])
    desc_path = project_path / "rawdata" / "dataset_description.json"

    if not desc_path.exists():
        return jsonify({
            "success": False,
            "error": "dataset_description.json not found"
        }), 404

    try:
        with open(desc_path, "r", encoding="utf-8") as f:
            description = json.load(f)

        # Validate on load
        issues = _project_manager.validate_dataset_description(description)

        return jsonify({
            "success": True,
            "description": description,
            "issues": issues
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to read dataset_description.json: {str(e)}"
        }), 500


@projects_bp.route("/api/projects/description", methods=["POST"])
def save_dataset_description():
    """Save the dataset_description.json for the current project."""
    import json

    current = get_current_project()
    if not current.get("path"):
        return jsonify({
            "success": False,
            "error": "No project selected"
        }), 400

    data = request.get_json()
    if not data or "description" not in data:
        return jsonify({
            "success": False,
            "error": "No description data provided"
        }), 400

    description = data["description"]
    project_path = Path(current["path"])
    desc_path = project_path / "rawdata" / "dataset_description.json"

    try:
        # Ensure name remains standard BIDS 'Name' (case sensitivity)
        if "Name" not in description and "name" in description:
            description["Name"] = description.pop("name")

        # Basic BIDS validation - ensure Name and BIDSVersion exist
        if "Name" not in description:
            return jsonify({"success": False, "error": "Dataset 'Name' is required"}), 400
        if "BIDSVersion" not in description:
            description["BIDSVersion"] = "1.10.1"

        # Validate before saving
        issues = _project_manager.validate_dataset_description(description)

        with open(desc_path, "w", encoding="utf-8") as f:
            json.dump(description, f, indent=2, ensure_ascii=False)

        # If name changed, also update session name for UI consistency
        if "Name" in description:
            set_current_project(str(project_path), description["Name"])

        return jsonify({
            "success": True,
            "message": "dataset_description.json saved successfully",
            "issues": issues
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to save dataset_description.json: {str(e)}"
        }), 500


@projects_bp.route("/api/projects/participants/columns", methods=["GET"])
def get_participants_columns():
    """Extract unique values from project's participants.tsv."""
    import pandas as pd
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"error": "No project selected"}), 400

    project_path = Path(current["path"])
    tsv_path = project_path / "rawdata" / "participants.tsv"

    if not tsv_path.exists():
        return jsonify({"columns": {}})

    try:
        df = pd.read_csv(tsv_path, sep='\t')
        result = {}
        for col in df.columns:
            # Always include the column to signal its availability in TSV
            # but only return unique values for categorical/low-cardinality columns
            if col.lower() not in ['participant_id', 'id'] and df[col].nunique() < 50:
                # Filter out NaNs and convert to strings
                unique_vals = [str(v) for v in df[col].dropna().unique().tolist()]
                result[col] = sorted(unique_vals)
            else:
                # Still include the key so frontend knows it exists in TSV
                result[col] = []

        return jsonify({"columns": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/participants/templates", methods=["GET"])
def get_participants_templates():
    """Get predefined BIDS-compatible field templates.

    Returns categorized field definitions with descriptions and levels.
    These are recommendations based on BIDS standard and common research needs.
    """
    # Predefined BIDS-compatible participant fields organized by category
    templates = {
        "required": {
            "participant_id": {
                "Description": "Unique participant identifier",
                "_help": "REQUIRED by BIDS. Format: sub-<label> (e.g., sub-001)",
                "_required": True
            }
        },
        "demographics": {
            "age": {
                "Description": "Age of participant",
                "Units": "years",
                "_help": "Recommended. Can be exact age or age range for anonymity."
            },
            "sex": {
                "Description": "Biological sex",
                "Levels": {
                    "M": "Male",
                    "F": "Female",
                    "O": "Other",
                    "DNS": "Did not say"
                },
                "_help": "BIDS recommended. Biological sex assigned at birth."
            },
            "gender": {
                "Description": "Gender identity",
                "Levels": {
                    "woman": "Woman",
                    "man": "Man",
                    "non_binary": "Non-binary",
                    "other": "Other",
                    "DNS": "Did not say"
                },
                "_help": "Self-identified gender. Separate from biological sex."
            },
            "handedness": {
                "Description": "Handedness",
                "Levels": {
                    "R": "Right",
                    "L": "Left",
                    "A": "Ambidextrous"
                },
                "_help": "BIDS recommended for neuroimaging studies."
            }
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
                    "7": "Other"
                },
                "_help": "Categorical education level."
            },
            "education_years": {
                "Description": "Years of formal education completed",
                "Units": "years",
                "_help": "Continuous measure of education."
            }
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
                    "other": "Other"
                }
            },
            "marital_status": {
                "Description": "Marital status",
                "Levels": {
                    "single": "Single",
                    "partnered": "Partnered",
                    "married": "Married",
                    "divorced": "Divorced",
                    "widowed": "Widowed"
                }
            },
            "household_size": {
                "Description": "Number of people in the household",
                "Units": "persons"
            }
        },
        "geographic": {
            "country_of_residence": {
                "Description": "Country of residence",
                "_help": "Use ISO 3166-1 alpha-2 codes (e.g., AT, DE, US)."
            },
            "native_language": {
                "Description": "Native language",
                "_help": "Use ISO 639-1 codes (e.g., de, en, fr)."
            }
        },
        "health": {
            "height": {
                "Description": "Body height",
                "Units": "cm"
            },
            "weight": {
                "Description": "Body weight",
                "Units": "kg"
            },
            "bmi": {
                "Description": "Body mass index",
                "Units": "kg/m^2"
            },
            "smoking_status": {
                "Description": "Smoking status",
                "Levels": {
                    "never": "Never smoked",
                    "former": "Former smoker",
                    "current": "Current smoker"
                }
            },
            "vision": {
                "Description": "Vision status",
                "Levels": {
                    "normal": "Normal/corrected to normal",
                    "impaired": "Impaired"
                },
                "_help": "Important for visual experiments."
            },
            "hearing": {
                "Description": "Hearing status",
                "Levels": {
                    "normal": "Normal",
                    "impaired": "Impaired"
                },
                "_help": "Important for auditory experiments."
            }
        },
        "study": {
            "group": {
                "Description": "Study group assignment",
                "Levels": {
                    "control": "Control group",
                    "experimental": "Experimental group"
                },
                "_help": "Define your study-specific groups."
            },
            "session_date": {
                "Description": "Date of data collection",
                "Units": "ISO 8601 date",
                "_help": "Format: YYYY-MM-DD"
            }
        }
    }

    # BIDS compliance tips
    tips = [
        {
            "level": "required",
            "message": "participant_id is REQUIRED by BIDS specification",
            "field": "participant_id"
        },
        {
            "level": "recommended",
            "message": "BIDS recommends including age, sex, and handedness for all datasets",
            "fields": ["age", "sex", "handedness"]
        },
        {
            "level": "info",
            "message": "Use standard units (years, cm, kg) and ISO codes for countries/languages",
            "fields": []
        },
        {
            "level": "info",
            "message": "Each field should have a Description. Use Levels for categorical data and Units for continuous data.",
            "fields": []
        },
        {
            "level": "privacy",
            "message": "Consider anonymization: use age ranges instead of exact ages, avoid identifying information",
            "fields": ["age", "country_of_residence"]
        }
    ]

    return jsonify({
        "success": True,
        "templates": templates,
        "tips": tips,
        "categories": list(templates.keys())
    })
