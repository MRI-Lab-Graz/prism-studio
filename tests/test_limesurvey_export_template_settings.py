"""What the Template Editor saves in an item's LimeSurvey settings (and what a LimeSurvey
import puts there) must reach the exported .lss: required, show-condition, help text,
"Other" option and text-box rows. The exporter used to read other keys (Relevance,
Help, Mandatory, OtherOption) and silently dropped these."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import defusedxml.ElementTree as DET  # noqa: E402

TEMPLATE = {
    "Study": {"OriginalName": "Settings", "Instructions": {"de": "Bitte antworten."}},
    "I18n": {"Languages": ["de", "en"], "DefaultLanguage": "de"},
    "consent": {
        "Description": {"de": "Einverstanden?", "en": "Agree?"},
        "Levels": {"1": {"de": "ja", "en": "yes"}, "2": {"de": "nein", "en": "no"}},
        "LimeSurvey": {"questionType": "L", "mandatory": True, "other": True},
    },
    "reason": {
        "Description": {"de": "Warum?", "en": "Why?"},
        "LimeSurvey": {
            "questionType": "T",
            "mandatory": False,
            "relevance": "((consent.NAOK == \"2\"))",
            "helpText": {"de": "Ein paar Worte", "en": "A few words"},
            "displayRows": 5,
        },
    },
}


def _export(tmp_path, exporter):
    from src.limesurvey_exporter import generate_lss, generate_lss_from_customization
    from src.survey_customizer import build_customizer_groups

    path = tmp_path / "survey-settings.json"
    path.write_text(json.dumps(TEMPLATE), encoding="utf-8")
    if exporter == "quick":
        xml = generate_lss([str(path)], languages=["de", "en"], base_language="de", matrix_mode=False)
    else:
        groups = build_customizer_groups([{"path": str(path)}], "de")
        xml = generate_lss_from_customization(
            groups, languages=["de", "en"], base_language="de", matrix_mode=False
        )
    root = DET.fromstring(xml)
    questions = {q.findtext("title"): q for q in root.findall("questions/rows/row")}
    help_text = {
        (row.findtext("qid"), row.findtext("language")): row.findtext("help")
        for row in root.findall("question_l10ns/rows/row")
    }
    attributes = {
        (row.findtext("qid"), row.findtext("attribute")): row.findtext("value")
        for row in root.findall("question_attributes/rows/row")
    }
    return questions, help_text, attributes


@pytest.mark.parametrize("exporter", ["quick", "customizer"])
def test_required_follows_the_template_editor_setting(tmp_path, exporter):
    questions, _help, _attrs = _export(tmp_path, exporter)
    assert questions["consent"].findtext("mandatory") == "Y"
    assert questions["reason"].findtext("mandatory") == "N"


@pytest.mark.parametrize("exporter", ["quick", "customizer"])
def test_show_condition_is_exported(tmp_path, exporter):
    questions, _help, _attrs = _export(tmp_path, exporter)
    assert questions["reason"].findtext("relevance") == "((consent.NAOK == \"2\"))"


@pytest.mark.parametrize("exporter", ["quick", "customizer"])
def test_help_text_is_exported_per_language(tmp_path, exporter):
    questions, help_text, _attrs = _export(tmp_path, exporter)
    qid = questions["reason"].findtext("qid")
    assert help_text[(qid, "de")] == "Ein paar Worte"
    assert help_text[(qid, "en")] == "A few words"


@pytest.mark.parametrize("exporter", ["quick", "customizer"])
def test_other_option_is_exported(tmp_path, exporter):
    questions, _help, _attrs = _export(tmp_path, exporter)
    assert questions["consent"].findtext("other") == "Y"


@pytest.mark.parametrize("exporter", ["quick", "customizer"])
def test_text_box_rows_are_exported(tmp_path, exporter):
    questions, _help, attributes = _export(tmp_path, exporter)
    assert attributes[(questions["reason"].findtext("qid"), "display_rows")] == "5"


def test_always_shown_relevance_does_not_hide_a_conditional_display():
    """The LimeSurvey import writes relevance "1" (always shown) on every item."""
    from src.limesurvey_exporter import _build_relevance_equation

    item = {"LimeSurvey": {"relevance": "1"}, "ConditionalDisplay": {"showWhen": "consent == '2'"}}
    assert _build_relevance_equation(item) == "((consent.NAOK == '2'))"
