import json

import pytest

from src.survey_fingerprints import fingerprint_sidecar, item_matches, scale_hash, wording_hashes


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


def test_wording_hash_collapses_whitespace_and_keeps_case():
    assert wording_hashes("I  feel\n fine", "en") == wording_hashes("I feel fine", "en")
    assert wording_hashes("I feel fine", "en") != wording_hashes("i feel fine", "en")
    assert wording_hashes("I feel fine.", "en") != wording_hashes("I feel fine", "en")


def test_wording_hashes_one_per_language_of_a_dict():
    h = wording_hashes({"en": "Hello", "de": "Hallo", "x": 5}, "en")
    assert set(h) == {"en", "de"}
    assert wording_hashes(None, "en") == {}


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
    col = {"Description": {"de": "Geheimer Text"}, "Levels": {"1": "x", "2": "y"}}
    assert item_matches(entry, col, "de") == ""
    assert item_matches(entry, {"Levels": {"1": "x", "2": "y"}}, "de") == ""  # no Description: scale alone
    assert item_matches(entry, {**col, "Levels": {"1": "x"}}, "de") == "changed scale"
    assert item_matches(entry, {**col, "Description": "Anderer Text"}, "de") == "changed wording"
    assert item_matches(entry, {**col, "Description": "Secret text"}, "fr") == "language not registered"
    assert item_matches(entry, {**col, "AliasOf": "Q9"}, "de") == "alias"
