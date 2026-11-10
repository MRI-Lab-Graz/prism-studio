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


# --- add_language -----------------------------------------------------------

from src.template_languages import add_language, template_languages  # noqa: E402


def test_template_languages_lists_declared_instruction_item_and_level_languages():
    tpl = _template()
    tpl["I18n"]["Languages"] = ["fr"]
    assert template_languages(tpl) == ["de", "en", "fr"]


def test_add_language_adds_empty_text_to_items_levels_and_instructions():
    out = add_language(_template(), "fr")
    assert out["ADS01"]["Description"]["fr"] == ""
    assert out["ADS01"]["Levels"]["0"]["fr"] == ""
    assert out["ADS01"]["VariantScales"][0]["Levels"]["0"]["fr"] == ""
    assert out["Study"]["Instructions"]["fr"] == ""
    assert out["I18n"]["Languages"] == ["de", "en", "fr"]


def test_add_language_leaves_the_header_alone():
    out = add_language(_template(), "fr")
    assert out["Study"]["OriginalName"] == {"en": "Depression Scale"}
    assert out["Study"]["Description"] == {"en": "A screening scale.", "de": ""}


def test_add_language_turns_plain_texts_into_the_original_language_entry():
    tpl = _template()
    tpl["ADS01"]["Description"] = "sad"
    tpl["ADS01"]["Levels"]["0"] = "never"
    out = add_language(tpl, "fr")
    assert out["ADS01"]["Description"] == {"en": "sad", "fr": ""}
    assert out["ADS01"]["Levels"]["0"] == {"en": "never", "fr": ""}


def test_add_language_sets_the_original_language_when_none_is_set():
    tpl = _template()
    del tpl["Technical"]["Language"]
    assert add_language(tpl, "fr")["Technical"]["Language"] == "fr"


def test_add_language_twice_changes_nothing_more():
    once = add_language(_template(), "fr")
    assert add_language(once, "fr") == once


@pytest.mark.parametrize("change, code", [(add_language, "fr"), (remove_language, "en")])
@pytest.mark.parametrize("section", ["Study", "Technical", "I18n"])
@pytest.mark.parametrize("junk", [[], "text", 5, None])
def test_sections_of_the_wrong_type_never_crash(change, code, section, junk):
    tpl = _template()
    tpl[section] = junk
    change(tpl, code)


@pytest.mark.parametrize("change, code", [(add_language, "fr"), (remove_language, "en")])
def test_junk_inside_items_and_the_language_list_never_crashes(change, code):
    tpl = _template()
    tpl["ADS01"]["VariantScales"] = 5
    tpl["I18n"]["Languages"] = ["en", ["x"], {"a": 1}, 3]
    assert "fr" in template_languages(add_language(tpl, "fr")) or change is remove_language
    change(tpl, code)


@pytest.mark.parametrize("action", ["add", "remove"])
@pytest.mark.parametrize("body", [[1], "x", 5, {}])
def test_routes_answer_400_for_a_body_that_is_not_a_template_request(action, body):
    import importlib
    from pathlib import Path

    from flask import Flask

    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.register_blueprint(importlib.import_module("src.web.blueprints.tools_template_editor_blueprint").tools_template_editor_bp)
    assert app.test_client().post(f"/api/template-editor/{action}-language", json=body).status_code == 400


def test_add_language_rejects_a_bad_code():
    for bad in ("", "english", "E1", 5):
        with pytest.raises(ValueError):
            add_language(_template(), bad)
