from app.src.web.blueprints.tools_template_editor_blueprint import (
    _autofill_single_version_variant_ids,
    _normalize_template_for_validation,
)
from app.src.web.blueprints.tools_helpers import _pick_enum_value
from app.src.utils.io import dump_json_text


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


def test_validation_normalization_drops_placeholder_variant_definitions_without_versions() -> (
    None
):
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


def test_validation_normalization_keeps_real_variant_definitions_for_multiple_versions() -> (
    None
):
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


def test_validation_normalization_autofills_bounds_from_contiguous_levels() -> None:
    template = {
        "Study": {"Versions": ["short"]},
        "Q01": {
            "Levels": {
                "0": {"en": "Strongly disagree"},
                "1": {"en": "Disagree"},
                "2": {"en": "Agree"},
            },
            "VariantScales": [
                {
                    "VariantID": "short",
                    "Levels": {
                        "1": {"en": "low"},
                        "2": {"en": "medium"},
                        "3": {"en": "high"},
                    },
                }
            ],
        },
    }

    out = _normalize_template_for_validation(modality="survey", template=template)

    assert out["Q01"]["MinValue"] == 0
    assert out["Q01"]["MaxValue"] == 2
    assert out["Q01"]["VariantScales"][0]["MinValue"] == 1
    assert out["Q01"]["VariantScales"][0]["MaxValue"] == 3


def test_dump_json_text_inlines_short_localized_level_entries() -> None:
    payload = {
        "BHPS01": {
            "Description": {"en": "I find it exciting to flirt with others"},
            "Levels": {
                "0": {"en": "never true"},
                "1": {"en": "seldom true"},
            },
        }
    }

    rendered = dump_json_text(payload)

    assert '"0": {"en": "never true"}' in rendered
    assert '"1": {"en": "seldom true"}' in rendered
    assert '"0": {\n' not in rendered
    assert (
        '"Description": {"en": "I find it exciting to flirt with others"}'
        not in rendered
    )
