from src.converters.pavlovia import (
    extract_questions,
    _resolve_text,
    _get_active_variant_id,
    _resolve_item_for_variant,
)


def test_extract_questions_reads_conditional_display_showwhen():
    prism_json = {
        "sex": {"Description": "Sex", "DataType": "string"},
        "pregnant": {
            "Description": "Are you pregnant?",
            "DataType": "string",
            "ConditionalDisplay": {"showWhen": "sex == 'F'"},
        },
    }
    questions = extract_questions(prism_json)
    by_code = {q["code"]: q for q in questions}
    assert by_code["pregnant"]["condition"] == "sex == 'F'"
    assert by_code["sex"]["condition"] is None


def test_extract_questions_prefers_explicit_relevance():
    prism_json = {
        "q1": {
            "Description": "Q1",
            "Relevance": "age >= 18",
            "ConditionalDisplay": {"showWhen": "sex == 'F'"},
        },
    }
    questions = extract_questions(prism_json)
    assert questions[0]["condition"] == "age >= 18"


def test_resolve_text_handles_plain_string():
    assert _resolve_text("Overall mood today", "en") == "Overall mood today"


def test_resolve_text_handles_language_dict():
    value = {"en": "Overall mood today", "de": "Stimmung heute"}
    assert _resolve_text(value, "de") == "Stimmung heute"


def test_resolve_text_falls_back_to_any_available_language():
    value = {"de": "Stimmung heute"}
    assert _resolve_text(value, "en") == "Stimmung heute"


def test_get_active_variant_id_reads_study_version():
    prism_json = {"Study": {"Version": "10-likert"}}
    assert _get_active_variant_id(prism_json) == "10-likert"


def test_get_active_variant_id_none_when_absent():
    assert _get_active_variant_id({"Study": {}}) is None
    assert _get_active_variant_id({}) is None


def test_resolve_item_for_variant_excludes_item_not_applicable():
    item = {"Description": "Q", "ApplicableVersions": ["7-likert"]}
    assert _resolve_item_for_variant(item, "10-likert") is None


def test_resolve_item_for_variant_includes_item_with_no_applicable_versions():
    item = {"Description": "Q"}
    assert _resolve_item_for_variant(item, "10-likert") == item


def test_resolve_item_for_variant_applies_variant_scale_override():
    item = {
        "Description": "Pain",
        "MinValue": 1,
        "MaxValue": 5,
        "ApplicableVersions": ["full", "short"],
        "VariantScales": [
            {"VariantID": "full", "ScaleType": "vas", "MinValue": 0, "MaxValue": 100},
        ],
    }
    resolved = _resolve_item_for_variant(item, "full")
    assert resolved["MinValue"] == 0
    assert resolved["MaxValue"] == 100
    assert resolved["ScaleType"] == "vas"


def test_resolve_item_for_variant_no_active_variant_does_not_exclude():
    item = {"Description": "Q", "ApplicableVersions": ["full"]}
    assert _resolve_item_for_variant(item, None) == item


def test_extract_questions_resolves_language_and_excludes_wrong_variant():
    prism_json = {
        "Study": {"Version": "full"},
        "rec_mood": {
            "Description": {"en": "Mood today", "de": "Stimmung heute"},
            "Levels": {"1": {"en": "Low", "de": "Niedrig"}, "2": {"en": "High", "de": "Hoch"}},
            "ApplicableVersions": ["full", "short"],
        },
        "rec_extra": {
            "Description": "Full-only item",
            "ApplicableVersions": ["full"],
        },
        "rec_gone": {
            "Description": "Not in this variant",
            "ApplicableVersions": ["short"],
        },
    }
    questions = extract_questions(prism_json)
    codes = {q["code"] for q in questions}
    assert codes == {"rec_mood", "rec_extra"}
    mood = next(q for q in questions if q["code"] == "rec_mood")
    assert mood["description"] == "Mood today"
    assert mood["levels"] == {"1": "Low", "2": "High"}
