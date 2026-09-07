from src.converters.pavlovia import (
    extract_questions,
    _resolve_text,
    _get_active_variant_id,
    _resolve_item_for_variant,
    determine_component_type,
    _safe_component_name,
    create_slider_component,
    create_textbox_component,
    build_psyexp_xml,
)
import xml.etree.ElementTree as ET


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


def test_determine_component_type_vas_scale_is_slider():
    q = {"levels": {}, "scale_type": "vas", "min_value": 0, "max_value": 100}
    assert determine_component_type(q) == "slider"


def test_determine_component_type_visual_analogue_is_slider():
    q = {"levels": {}, "scale_type": "visual-analogue"}
    assert determine_component_type(q) == "slider"


def test_determine_component_type_few_levels_is_radio():
    q = {"levels": {"1": "Low", "2": "High"}, "scale_type": None}
    assert determine_component_type(q) == "radio"


def test_determine_component_type_many_levels_is_dropdown():
    q = {"levels": {str(i): f"L{i}" for i in range(12)}, "scale_type": None}
    assert determine_component_type(q) == "dropdown"


def test_determine_component_type_no_levels_is_free_text():
    q = {"levels": {}, "scale_type": None}
    assert determine_component_type(q) == "free_text"


def test_safe_component_name_replaces_invalid_characters():
    assert _safe_component_name("rec-mood.1") == "rec_mood_1"
    assert _safe_component_name("rec_mood") == "rec_mood"


def test_create_slider_component_uses_min_max():
    q = {"code": "rec_pain", "description": "Pain", "min_value": 0, "max_value": 100}
    comp = create_slider_component(q)
    assert comp["name"] == "rec_pain"
    assert "0" in comp["ticks"] and "100" in comp["ticks"]


def test_create_textbox_component_basic():
    q = {"code": "notes", "description": "Anything else?"}
    comp = create_textbox_component(q)
    assert comp["name"] == "notes"
    assert comp["prompt"] == "Anything else?"


def _sample_questions():
    return [
        {
            "code": "rec_mood", "description": "Mood", "levels": {"1": "Low", "2": "High"},
            "scale_type": None, "min_value": None, "max_value": None,
            "mandatory": True, "condition": None,
        },
        {
            "code": "rec_pain", "description": "Pain", "levels": {},
            "scale_type": "vas", "min_value": 0, "max_value": 100,
            "mandatory": True, "condition": None,
        },
        {
            "code": "notes", "description": "Notes", "levels": {},
            "scale_type": None, "min_value": None, "max_value": None,
            "mandatory": False, "condition": "rec_mood == '1'",
        },
    ]


def test_build_psyexp_xml_is_well_formed():
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)  # raises if malformed
    assert root.tag == "PsychoPy2experiment"


def test_build_psyexp_xml_routes_slider_component():
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    slider_names = [
        c.get("name") for c in root.iter("SliderComponent")
    ]
    assert "rec_pain" in slider_names


def test_build_psyexp_xml_routes_textbox_component():
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    textbox_names = [c.get("name") for c in root.iter("TextboxComponent")]
    assert "notes" in textbox_names


def test_build_psyexp_xml_adds_code_component_for_conditional_question():
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    code_components = list(root.iter("CodeComponent"))
    assert len(code_components) == 1
    assert code_components[0].get("name") == "notes_condition"


def test_build_psyexp_xml_single_routine_for_all_questions():
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    # Scoped to the <Routines> container: root.iter("Routine") alone would
    # also match the Flow section's same-tag, same-name routine *reference*
    # pointer (0 children, vs. the real definition's populated children),
    # double-counting "questions" the same way "welcome"/"thanks" already
    # appear once in each section.
    routines_section = root.find("Routines")
    question_routines = [
        r for r in routines_section.iter("Routine") if r.get("name") not in ("welcome", "thanks")
    ]
    assert len(question_routines) == 1
