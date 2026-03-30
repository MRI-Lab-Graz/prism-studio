from app.src.web.blueprints.tools_template_editor_blueprint import (
    _autofill_single_version_variant_ids,
    _normalize_template_for_validation,
)
from app.src.web.blueprints.tools_helpers import _pick_enum_value


def test_autofill_variant_ids_from_single_versions_list() -> None:
    template = {
        "Study": {
            "Versions": ["short"],
            "VariantDefinitions": [{"VariantID": ""}, {"VariantID": "short"}],
        },
        "Q01": {"VariantScales": [{"VariantID": ""}, {"VariantID": "short"}]},
    }

    out = _autofill_single_version_variant_ids(template)

    assert out["Study"]["VariantDefinitions"][0]["VariantID"] == "short"
    assert out["Q01"]["VariantScales"][0]["VariantID"] == "short"


def test_does_not_autofill_when_multiple_versions_exist() -> None:
    template = {
        "Study": {
            "Versions": ["short", "long"],
            "VariantDefinitions": [{"VariantID": ""}],
        },
        "Q01": {"VariantScales": [{"VariantID": ""}]},
    }

    out = _autofill_single_version_variant_ids(template)

    assert out["Study"]["VariantDefinitions"][0]["VariantID"] == ""
    assert out["Q01"]["VariantScales"][0]["VariantID"] == ""


def test_autofill_uses_study_version_when_versions_absent() -> None:
    template = {
        "Study": {
            "Version": "v1",
            "VariantDefinitions": [{"VariantID": ""}],
        },
        "Q01": {"VariantScales": [{"VariantID": ""}]},
    }

    out = _autofill_single_version_variant_ids(template)

    assert out["Study"]["VariantDefinitions"][0]["VariantID"] == "v1"
    assert out["Q01"]["VariantScales"][0]["VariantID"] == "v1"


def test_validation_normalization_drops_placeholder_variant_definitions_without_versions() -> None:
    template = {
        "Study": {
            "VariantDefinitions": [
                {
                    "VariantID": "",
                    "ItemCount": 0,
                    "ScaleType": "likert",
                    "Description": {"en": ""},
                }
            ]
        }
    }

    out = _normalize_template_for_validation(modality="survey", template=template)

    assert "VariantDefinitions" not in out["Study"]


def test_validation_normalization_keeps_real_variant_definitions_for_multiple_versions() -> None:
    template = {
        "Study": {
            "Versions": ["short", "long"],
            "VariantDefinitions": [
                {
                    "VariantID": "",
                    "ItemCount": 10,
                    "ScaleType": "likert",
                    "Description": {"en": "Screening form"},
                }
            ],
        }
    }

    out = _normalize_template_for_validation(modality="survey", template=template)

    assert out["Study"]["VariantDefinitions"] == template["Study"]["VariantDefinitions"]


def test_pick_enum_value_prefers_blank_option_for_new_templates() -> None:
    assert _pick_enum_value(["LimeSurvey", "Other", ""]) == ""