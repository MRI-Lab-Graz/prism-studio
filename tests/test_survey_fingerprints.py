import json

import pytest

from src.survey_fingerprints import fingerprint_sidecar, item_matches, normalize_text, scale_hash, wording_hashes


def test_scale_hash_ignores_level_labels_and_order():
    a = {"Levels": {"1": "no", "2": "yes"}}
    b = {"Levels": {"2": "Ja", "1": "Nein"}}
    assert scale_hash(a) == scale_hash(b)
    assert len(scale_hash(a)) == 64


def test_scale_hash_treats_1_and_1_0_alike_but_not_01():
    assert scale_hash({"Levels": {1: "a"}}) == scale_hash({"Levels": {1.0: "a"}})
    assert scale_hash({"Levels": {"1": "a"}}) != scale_hash({"Levels": {"01": "a"}})
    assert scale_hash({"MinValue": 1.0}) == scale_hash({"MinValue": 1})
    assert scale_hash({"MinValue": 1}) != scale_hash({"MinValue": 2})


def _w(description, language="en"):
    return wording_hashes({"Description": description}, language)


def test_wording_hash_collapses_whitespace_case_and_punctuation():
    assert _w("I  feel\n fine") == _w("I feel fine")
    assert _w("I feel fine") == _w("i feel fine")
    assert _w("I feel fine.") == _w("I feel fine")
    assert _w("I feel fine") != _w("I feel well")


def test_wording_hashes_one_per_language_of_a_dict():
    h = wording_hashes({"Description": {"en": "Hello", "de": "Hallo", "x": 5}}, "en")
    assert set(h) == {"en", "de"}
    assert wording_hashes({}, "en") == {}


def test_normalize_text():
    assert normalize_text("  I don\u2019t FEEL fine\u2026 \u2013 really. ") == normalize_text("i don't feel fine - really")
    assert normalize_text("well-being") == normalize_text("well being")
    assert normalize_text("\uff21") == normalize_text("a")


def test_two_typings_of_one_item_match():
    first = {"Description": "I feel \u201csad\u201d.", "Levels": {"1": "no", "2": "yes"}}
    second = {"Description": 'i feel "sad"', "Levels": {"1": "no", "2": "yes"}}
    entry = fingerprint_sidecar({"Study": {"TaskName": "t"}, "Q1": first})["Items"]["Q1"]
    assert item_matches(entry, second, "en") == ""


def test_reversed_scale_is_changed_wording():
    a = {"Description": "Q", "Levels": {"1": "never", "2": "always"}}
    b = {"Description": "Q", "Levels": {"1": "always", "2": "never"}}
    assert scale_hash(a) == scale_hash(b)
    entry = fingerprint_sidecar({"Study": {"TaskName": "t"}, "Q1": a})["Items"]["Q1"]
    assert item_matches(entry, b, "en") == "changed wording"


def test_labels_in_every_shape():
    item = {"Description": {"en": "x", "de": "y"}, "Levels": {"1": "plain", "2": {"en": "a", "de": "b"}, "3": 5}}
    assert set(wording_hashes(item, "en")) == {"en", "de"}


def test_item_without_description_still_matches_on_scale():
    item = {"Levels": {"1": "a", "2": "b"}}
    assert wording_hashes(item, "en") == {}
    entry = fingerprint_sidecar({"Study": {"TaskName": "t"}, "Q1": {"Description": "x", **item}})["Items"]["Q1"]
    assert item_matches(entry, item, "en") == ""


SIDECAR = {
    "Study": {"TaskName": "My_Task"},
    "Technical": {"Language": "de"},
    "@context": {"a": "b"},
    "Q1": {"Description": {"de": "Geheimer Text", "en": "Secret text"}, "Levels": {"1": "a", "2": "b"},
           "VariantScales": [{"Levels": {"1": "a", "2": "b"}}, {"MinValue": 1, "MaxValue": 7}]},
    "Q2": {"Description": "Noch ein Text", "AliasOf": "Q1"},
    "Q3": {"Description": "Dritter Text", "MinValue": 0},
    "Q4": "not a dict",
}


def test_fingerprint_sidecar_includes_variant_scales():
    fp = fingerprint_sidecar(SIDECAR)
    assert fp["Version"] == 1 and fp["Task"] == "my-task"
    assert len(fp["Items"]["Q1"]["Scales"]) == 2  # duplicate variant dropped
    assert fp["Items"]["Q1"]["Scales"][0] == scale_hash(SIDECAR["Q1"])
    assert set(fp["Items"]["Q1"]["Wording"]) == {"de", "en"}


def test_fingerprint_sidecar_skips_alias_and_non_items():
    assert set(fingerprint_sidecar(SIDECAR)["Items"]) == {"Q1", "Q3"}


def test_fingerprint_sidecar_language_selects_one_or_raises():
    assert set(fingerprint_sidecar(SIDECAR, "en")["Items"]["Q1"]["Wording"]) == {"en"}
    with pytest.raises(ValueError):
        fingerprint_sidecar(SIDECAR, "fr")
    plain = {"Study": {"TaskName": "t"}, "Q": {"Description": "x"}}
    assert fingerprint_sidecar(plain, "en")["Items"]["Q"]["Wording"]
    with pytest.raises(ValueError):
        fingerprint_sidecar(plain, "de")


def test_fingerprint_holds_no_item_text():
    dump = json.dumps(fingerprint_sidecar(SIDECAR), ensure_ascii=False)
    for text in ("Geheimer Text", "Secret text", "Dritter Text"):
        assert text not in dump


def test_item_matches_reasons():
    entry = fingerprint_sidecar(SIDECAR)["Items"]["Q1"]
    col = {"Description": {"de": "Geheimer Text"}, "Levels": {"1": "a", "2": "b"}}
    assert item_matches(entry, col, "de") == ""
    assert item_matches(entry, {"Levels": {"1": "x", "2": "y"}}, "de") == ""  # no Description: scale alone
    assert item_matches(entry, {**col, "Levels": {"1": "x"}}, "de") == "changed scale"
    assert item_matches(entry, {**col, "Description": "Anderer Text"}, "de") == "changed wording"
    assert item_matches(entry, {**col, "Description": "Secret text"}, "fr") == "language not registered"
    assert item_matches(entry, {**col, "AliasOf": "Q9"}, "de") == "alias"


@pytest.mark.parametrize("weird", [
    {"Description": ["a", "b"], "Levels": {"1": "x"}},
    {"Description": 5, "Levels": {"1": "x"}},
    {"Description": {"en": "t"}, "Levels": ["1", "2"]},
    {"Description": {"en": "t"}, "VariantScales": "abc"},
    {"Description": {"en": "t"}, "VariantScales": [5, None]},
    {"Description": {"en": "t"}, "Levels": {"1": "x"}, "MinValue": "a", "MaxValue": [1]},
])
def test_weird_items_never_raise(weird):
    fingerprint_sidecar({"Study": {"TaskName": "t"}, "Q1": weird})


@pytest.mark.parametrize("top", [{"Study": ["x"]}, {"Technical": {"Language": 5}}, {"Technical": ["en"]}, {"Study": {"TaskName": 5}}])
def test_weird_headers_never_raise(top):
    fingerprint_sidecar({**top, "Q1": {"Description": {"en": "t"}}})
