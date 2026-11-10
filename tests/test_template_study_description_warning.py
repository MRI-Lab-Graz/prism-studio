"""Templates made by older Excel imports carry the first item's text as Study.Description; say so."""

from src.template_save import template_warnings


def _template(study_description):
    return {
        "Study": {"TaskName": "ads", "OriginalName": {"en": "Scale"}, "Description": study_description},
        "I18n": {"Languages": ["en"]},
        "Technical": {"Language": "en"},
        "ADS01": {"Description": {"en": "I feel sad"}, "Levels": {"0": {"en": "no"}, "1": {"en": "yes"}}},
        "ADS02": {"Description": {"en": "I cannot sleep"}, "Levels": {"0": {"en": "no"}, "1": {"en": "yes"}}},
    }


def _messages(template):
    language, items = template_warnings(template)
    return [w["message"] for w in language + items]


def test_a_study_description_copied_from_an_item_is_reported():
    messages = _messages(_template({"en": "I feel sad"}))
    assert any("Study.Description" in m and "ADS01" in m for m in messages)


def test_a_plain_string_copy_is_reported_too():
    assert any("Study.Description" in m for m in _messages(_template("I cannot sleep")))


def test_a_one_item_template_may_describe_itself_with_its_only_item():
    tpl = _template({"en": "I feel sad"})
    del tpl["ADS02"]
    assert not any("Study.Description" in m for m in _messages(tpl))


def test_a_real_study_description_is_not_reported():
    assert not any("Study.Description" in m for m in _messages(_template({"en": "A depression screening scale."})))
