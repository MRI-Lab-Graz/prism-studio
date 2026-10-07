"""Pure CITATION.cff validation (no Studio imports; ships in the validator wheel)."""

import datetime as dt

from src.citation_cff import normalize_dates, validate_citation_cff_file

VALID = """cff-version: 1.2.0
message: Please cite this dataset.
title: Test
authors:
  - family-names: Doe
    given-names: Jane
version: 1.0.0
date-released: {date}
"""


def _write(tmp_path, text):
    p = tmp_path / "CITATION.cff"
    p.write_text(text, encoding="utf-8")
    return p


def test_missing_file(tmp_path):
    r = validate_citation_cff_file(tmp_path / "CITATION.cff")
    assert r["exists"] is False and r["valid"] is False
    assert r["issues"] == ["CITATION.cff is missing at the dataset root."]


def test_unreadable_file(tmp_path):
    p = tmp_path / "CITATION.cff"
    p.write_bytes(b"\xff\xfe\x00bad")
    r = validate_citation_cff_file(p)
    assert r["exists"] and not r["valid"]
    assert r["issues"][0].startswith("CITATION.cff could not be read:")


def test_invalid_yaml(tmp_path):
    r = validate_citation_cff_file(_write(tmp_path, "a: [unclosed\n"))
    assert r["issues"][0].startswith("CITATION.cff is not valid YAML:")


def test_list_at_root(tmp_path):
    r = validate_citation_cff_file(_write(tmp_path, "- a\n- b\n"))
    assert r["issues"] == ["CITATION.cff must contain a YAML mapping at its root."]


def test_unquoted_date_is_valid(tmp_path):
    r = validate_citation_cff_file(_write(tmp_path, VALID.format(date="2026-01-01")))
    assert r["issues"] == [] and r["valid"] is True
    assert r["parsed"]["date-released"] == "2026-01-01"


def test_quoted_date_is_valid(tmp_path):
    r = validate_citation_cff_file(_write(tmp_path, VALID.format(date="'2026-01-01'")))
    assert r["valid"] is True


def test_missing_required_properties(tmp_path):
    r = validate_citation_cff_file(
        _write(tmp_path, "cff-version: 1.2.0\nmessage: hi\n")
    )
    text = " ".join(r["issues"])
    assert not r["valid"]
    assert "'title' is a required property" in text
    assert "'authors' is a required property" in text


def test_bad_date_is_reported(tmp_path):
    r = validate_citation_cff_file(_write(tmp_path, VALID.format(date="yesterday")))
    assert not r["valid"]
    assert any(i.startswith("date-released:") for i in r["issues"])


def test_normalize_dates_converts_nested_and_keeps_rest():
    data = {
        "a": dt.date(2026, 1, 2),
        "b": [dt.datetime(2026, 1, 2), {"c": dt.datetime(2026, 1, 2, 3, 4, 5)}],
        "d": "x",
        "e": 5,
        "f": None,
    }
    assert normalize_dates(data) == {
        "a": "2026-01-02",
        "b": ["2026-01-02", {"c": "2026-01-02T03:04:05"}],
        "d": "x",
        "e": 5,
        "f": None,
    }
