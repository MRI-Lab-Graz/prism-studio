from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _load_helpers_module():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    return importlib.import_module("src.web.blueprints.tools_helpers")


def _survey_technical_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "Technical": {
                "type": "object",
                "properties": {
                    "SoftwarePlatform": {
                        "type": "string",
                        "enum": [
                            "LimeSurvey",
                            "PsychoPy",
                            "Pavlovia",
                            "Paper and Pencil",
                            "Other",
                            "",
                        ],
                    },
                    "SoftwareVersion": {"type": "string"},
                    "AdministrationMethod": {"type": "string"},
                },
                "required": ["SoftwarePlatform", "AdministrationMethod"],
            }
        },
        "required": ["Technical"],
    }


def test_validate_against_schema_ignores_legacy_platform_for_paper_admin():
    helpers = _load_helpers_module()

    payload = {
        "Technical": {
            "SoftwarePlatform": "Legacy/Imported",
            "SoftwareVersion": "",
            "AdministrationMethod": "paper",
        }
    }

    errors = helpers._validate_against_schema(
        instance=payload,
        schema=_survey_technical_schema(),
    )
    paths = {err.get("path", "") for err in errors}

    assert "Technical/SoftwarePlatform" not in paths
    assert "Technical/SoftwareVersion" not in paths


def test_validate_against_schema_requires_software_version_for_non_paper():
    helpers = _load_helpers_module()

    payload = {
        "Technical": {
            "SoftwarePlatform": "Other",
            "SoftwareVersion": "",
            "AdministrationMethod": "online",
        }
    }

    errors = helpers._validate_against_schema(
        instance=payload,
        schema=_survey_technical_schema(),
    )

    assert any(
        err.get("path") == "Technical/SoftwareVersion"
        and "SoftwareVersion is required" in err.get("message", "")
        for err in errors
    )


def test_validate_against_schema_keeps_legacy_platform_error_for_non_paper():
    helpers = _load_helpers_module()

    payload = {
        "Technical": {
            "SoftwarePlatform": "Legacy/Imported",
            "SoftwareVersion": "",
            "AdministrationMethod": "online",
        }
    }

    errors = helpers._validate_against_schema(
        instance=payload,
        schema=_survey_technical_schema(),
    )

    assert any(err.get("path") == "Technical/SoftwarePlatform" for err in errors)
