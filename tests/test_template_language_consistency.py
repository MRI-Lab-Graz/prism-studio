"""Declared languages (I18n.Languages) against what the template says (spec B.5)."""

from src.template_validator import TemplateValidator

CHECK = TemplateValidator.validate_language_consistency_from_data


def _template(languages, **extra):
    return {
        "Technical": {"Language": "en"},
        "I18n": {"Languages": languages},
        "Study": {"OriginalName": {"en": "x"}},
        "pss_01": {"Description": {"en": "q", "de": "f"}, "Levels": {"0": {"en": "no", "de": "nein"}}},
        **extra,
    }


def _messages(template):
    return [f["message"] for f in CHECK(template)]


def test_a_consistent_template_has_no_finding():
    assert CHECK(_template(["en", "de"])) == []


def test_an_item_without_a_declared_language_text_is_reported():
    template = _template(["en", "de"])
    template["pss_02"] = {"Description": {"en": "q"}}
    assert "Item pss_02 has no 'de' text (declared in I18n.Languages)" in _messages(template)


def test_a_level_without_a_declared_language_text_is_reported():
    template = _template(["en", "de"])
    template["pss_01"]["Levels"]["1"] = {"en": "yes", "de": " "}
    assert any(m.startswith("Item pss_01") and "'de'" in m for m in _messages(template))


def test_an_undeclared_language_key_is_reported():
    template = _template(["en", "de"])
    template["pss_03"] = {"Description": {"en": "q", "de": "f", "fr": "?"}}
    assert "'fr' is used in pss_03 but not declared in I18n.Languages" in _messages(template)


def test_technical_language_and_default_language_must_be_declared():
    template = _template(["de"])
    template["I18n"]["DefaultLanguage"] = "en"
    template["pss_01"] = {"Description": {"de": "f"}}
    findings = CHECK(template)
    assert {"Technical/Language", "I18n/DefaultLanguage"} <= {f["path"] for f in findings}


def test_study_texts_only_in_english_are_fine_when_english_is_not_declared():
    template = _template(["de"])
    template["Technical"]["Language"] = "de"
    template["pss_01"] = {"Description": {"de": "f"}}
    assert CHECK(template) == []
