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
    assert "Item pss_02 has no 'de' text for: description (declared in I18n.Languages)" in _messages(template)


def test_a_level_without_a_declared_language_text_is_reported():
    template = _template(["en", "de"])
    template["pss_01"]["Levels"]["1"] = {"en": "yes", "de": " "}
    assert "Item pss_01 has no 'de' text for: levels 1 (declared in I18n.Languages)" in _messages(template)


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


def test_gaps_are_one_finding_per_language_and_item():
    template = _template(["en", "de", "fr"])
    template["pss_01"]["Levels"]["1"] = {"en": "yes", "de": "ja"}
    findings = [f for f in CHECK(template) if "text for:" in f["message"]]
    assert sorted(f["message"] for f in findings) == [
        "Item pss_01 has no 'fr' text for: description, levels 0, 1 (declared in I18n.Languages)"
    ]


def test_severity_per_finding_kind():
    template = _template(["de"])
    template["pss_01"]["Description"]["fr"] = "?"
    by_kind = {}
    for f in CHECK(template):
        kind = "undeclared" if "not declared" in f["message"] else "gap" if "text for:" in f["message"] else "technical"
        by_kind.setdefault(kind, set()).add(f["severity"])
    assert by_kind["undeclared"] == {"error"}
    assert by_kind["technical"] == {"warning"}


def test_superseding_drops_the_older_overlapping_checks_only_when_languages_are_declared():
    template = _template(["en", "de"])
    template["Technical"]["Language"] = "fr"
    older = CHECK(template)
    superseded = TemplateValidator.validate_language_consistency_from_data(template, supersede_declared=True)
    assert len(older) > len(superseded)
    assert [f["path"] for f in superseded].count("Technical/Language") == 1
    undeclared = {"I18n": {}, "pss_01": {"Description": {"en": "a"}}, "pss_02": {"Description": {"de": "b"}}}
    assert TemplateValidator.validate_language_consistency_from_data(undeclared, supersede_declared=True) == CHECK(undeclared)
