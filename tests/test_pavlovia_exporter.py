import json
from src.converters.pavlovia import (
    extract_questions,
    _resolve_text,
    _get_active_variant_id,
    _resolve_item_for_variant,
    determine_component_type,
    _safe_component_name,
    create_slider_component,
    create_textbox_component,
    create_conditions_csv,
    build_psyexp_xml,
    export_to_pavlovia,
)
import xml.etree.ElementTree as ET
import pandas as pd


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


def test_create_conditions_csv_populates_question_type(tmp_path):
    """question_type must come from determine_component_type, not the dead
    'type' key extract_questions never produces (see review: this used to
    always be an empty string)."""
    questions = [
        {"code": "rec_mood", "description": "Mood", "levels": {"1": "Low", "2": "High"}},
        {"code": "rec_pain", "description": "Pain", "levels": {}, "scale_type": "vas"},
        {"code": "notes", "description": "Notes", "levels": {}},
    ]
    csv_path = create_conditions_csv(questions, tmp_path)
    df = pd.read_csv(csv_path)
    by_code = df.set_index("question_code")["question_type"].to_dict()
    assert by_code["rec_mood"] == "radio"
    assert by_code["rec_pain"] == "slider"
    assert by_code["notes"] == "free_text"


def test_create_conditions_csv_no_dead_items_expansion(tmp_path):
    """An 'items' key (a fictional array-subquestion concept extract_questions
    never emits) must not be treated specially -- one row per question."""
    questions = [
        {"code": "q1", "description": "Q1", "levels": {}, "items": {"01": {}}},
    ]
    csv_path = create_conditions_csv(questions, tmp_path)
    df = pd.read_csv(csv_path)
    assert len(df) == 1
    assert df.iloc[0]["question_code"] == "q1"
    assert "parent_code" not in df.columns


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


def test_build_psyexp_xml_condition_code_surfaces_text_not_bool_eval():
    """The CodeComponent must not lie about gating visibility (see review):

    it should surface the literal condition text as a comment for a
    researcher to translate, not evaluate bool() on the condition string
    (which is truthy for any non-empty string and never actually gates
    anything).
    """
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    code_component = next(root.iter("CodeComponent"))
    begin_routine_val = next(
        p.get("val") for p in code_component.iter("Param")
        if p.get("name") == "Begin Routine"
    )
    assert "rec_mood == '1'" in begin_routine_val
    assert "bool('rec_mood == \\'1\\'')" not in begin_routine_val
    assert "bool(" not in begin_routine_val


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


def test_export_to_pavlovia_end_to_end(tmp_path):
    """A realistic bilingual, two-variant template exports cleanly."""
    prism_json = {
        "I18n": {"Languages": ["en", "de"], "DefaultLanguage": "en"},
        "Study": {"TaskName": "recovery", "Version": "full"},
        "rec_mood": {
            "Description": {"en": "Overall mood today", "de": "Stimmung heute"},
            "Levels": {
                "1": {"en": "Not at all", "de": "Gar nicht"},
                "2": {"en": "Slightly", "de": "Etwas"},
            },
            "DataType": "integer", "MinValue": 1, "MaxValue": 2,
            "ApplicableVersions": ["full", "short"],
        },
        "rec_pain": {
            "Description": {"en": "Pain intensity", "de": "Schmerzintensitaet"},
            "DataType": "integer", "MinValue": 0, "MaxValue": 100,
            "ApplicableVersions": ["full", "short"],
            "VariantScales": [
                {"VariantID": "full", "ScaleType": "vas", "MinValue": 0, "MaxValue": 100},
            ],
        },
        "rec_extra": {
            "Description": {"en": "Full-only extra item"},
            "ApplicableVersions": ["full"],
        },
        "rec_notes": {
            "Description": {"en": "Anything else?"},
            "Mandatory": False,
        },
    }
    json_path = tmp_path / "task-recovery_survey.json"
    json_path.write_text(json.dumps(prism_json), encoding="utf-8")

    psyexp_path = export_to_pavlovia(json_path, tmp_path / "out")

    assert psyexp_path.exists()
    root = ET.fromstring(psyexp_path.read_text(encoding="utf-8"))

    slider_names = [c.get("name") for c in root.iter("SliderComponent")]
    assert "rec_pain" in slider_names  # vas override applied

    textbox_names = [c.get("name") for c in root.iter("TextboxComponent")]
    assert "rec_notes" in textbox_names  # no Levels -> free text

    # rec_mood's English label made it through (default language resolution)
    all_param_values = " ".join(
        p.get("val", "") for p in root.iter("Param")
    )
    assert "Overall mood today" in all_param_values
    assert "Stimmung heute" not in all_param_values  # German NOT exported (single-language scope)


def test_export_to_pavlovia_explicit_language_overrides_default(tmp_path):
    """An explicit language= must override the template's own
    I18n.DefaultLanguage (see review: this was previously unwired end to
    end -- the GUI's Base Language dropdown had no effect)."""
    prism_json = {
        "I18n": {"Languages": ["en", "de"], "DefaultLanguage": "en"},
        "Study": {"TaskName": "recovery"},
        "rec_mood": {"Description": {"en": "Overall mood today", "de": "Stimmung heute"}},
    }
    json_path = tmp_path / "task-recovery_survey.json"
    json_path.write_text(json.dumps(prism_json), encoding="utf-8")

    psyexp_path = export_to_pavlovia(json_path, tmp_path / "out", language="de")

    all_param_values = " ".join(
        p.get("val", "") for p in ET.fromstring(psyexp_path.read_text(encoding="utf-8")).iter("Param")
    )
    assert "Stimmung heute" in all_param_values
    assert "Overall mood today" not in all_param_values
