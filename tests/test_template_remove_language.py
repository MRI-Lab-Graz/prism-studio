"""Remove Language: items and levels lose the language, the general header never does."""

import copy

import pytest

from src.template_languages import remove_language


def _template():
    return {
        "Technical": {"Language": "en", "StimulusType": "Questionnaire"},
        "I18n": {"Languages": ["de", "en"], "DefaultLanguage": "en"},
        "Study": {
            "TaskName": "ads",
            "OriginalName": {"en": "Depression Scale"},  # German left blank: only English is filled
            "Description": {"en": "A screening scale.", "de": ""},
            "Citation": "Hautzinger 1993",
            "Instructions": {"de": "Bitte antworten.", "en": "Please answer."},
        },
        "Metadata": {"SchemaVersion": "1.0"},
        "ADS01": {
            "Description": {"de": "traurig", "en": "sad"},
            "Levels": {"0": {"de": "nie", "en": "never"}, "1": {"de": "oft", "en": "often"}},
            "VariantScales": [{"Levels": {"0": {"de": "nie", "en": "never"}}}],
        },
    }


def test_header_fields_keep_every_language():
    out = remove_language(_template(), "en")
    assert out["Study"]["OriginalName"] == {"en": "Depression Scale"}
    assert out["Study"]["Description"] == {"en": "A screening scale.", "de": ""}
    assert out["Technical"]["Language"] == "en"


def test_items_and_levels_lose_the_language():
    out = remove_language(_template(), "en")
    assert out["ADS01"]["Description"] == "traurig"
    assert out["ADS01"]["Levels"]["1"] == "oft"
    assert out["ADS01"]["VariantScales"][0]["Levels"]["0"] == "nie"


def test_instructions_follow_the_items():
    out = remove_language(_template(), "en")
    assert out["Study"]["Instructions"] == {"de": "Bitte antworten."}


def test_instructions_never_end_up_empty():
    tpl = _template()
    tpl["Study"]["Instructions"] = {"en": "Please answer."}
    assert remove_language(tpl, "en")["Study"]["Instructions"] == {"en": "Please answer."}


def test_default_language_moves_to_a_remaining_language():
    out = remove_language(_template(), "en")
    assert out["I18n"] == {"Languages": ["de"], "DefaultLanguage": "de"}


def test_removing_the_last_language_drops_the_default():
    tpl = _template()
    tpl["I18n"] = {"Languages": ["en"], "DefaultLanguage": "en"}
    assert remove_language(tpl, "en")["I18n"] == {"Languages": []}


def test_input_is_not_modified():
    tpl = _template()
    before = copy.deepcopy(tpl)
    remove_language(tpl, "en")
    assert tpl == before


def test_rejects_an_empty_code():
    with pytest.raises(ValueError):
        remove_language(_template(), "")


def test_rejects_input_that_is_not_a_template_or_a_language_code():
    with pytest.raises(ValueError):
        remove_language([], "en")
    with pytest.raises(ValueError):
        remove_language({}, 5)


def test_a_template_without_declared_languages_gets_none_invented():
    tpl = _template()
    tpl["I18n"] = {"DefaultLanguage": "en"}
    assert remove_language(tpl, "en")["I18n"] == {"DefaultLanguage": "en"}


def test_context_and_task_keys_are_not_items():
    tpl = _template()
    tpl["@context"] = {"Description": {"en": "x", "de": "y"}}
    assert remove_language(tpl, "en")["@context"] == tpl["@context"]
