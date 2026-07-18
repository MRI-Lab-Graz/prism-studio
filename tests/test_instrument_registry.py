"""Tests for the instrument registry (roadmap Phase 4)."""

from pathlib import Path

from src.instrument_registry import (
    build_registry_index,
    get_instrument_identity,
    load_registry_index,
    write_registry_index,
)

OFFICIAL_SURVEY_DIR = (
    Path(__file__).resolve().parent.parent / "official" / "library" / "survey"
)


def test_build_registry_index_covers_all_official_instruments():
    index = build_registry_index(OFFICIAL_SURVEY_DIR)
    expected_count = len(
        [
            p
            for p in OFFICIAL_SURVEY_DIR.glob("survey-*.json")
            if "participant" not in p.stem.lower()
        ]
    )
    assert len(index["Instruments"]) == expected_count
    assert expected_count > 0


def test_known_instrument_resolves_expected_fields():
    index = build_registry_index(OFFICIAL_SURVEY_DIR)
    aai = index["Instruments"]["aai"]
    assert aai["TaskName"] == "aai"
    assert aai["SourceFile"] == "survey-aai.json"
    assert aai["ShortName"] == "AAI"
    assert "Veale" in aai["Citation"]


def test_write_and_load_registry_index_roundtrip(tmp_path):
    index_path = tmp_path / "index.json"
    written = write_registry_index(OFFICIAL_SURVEY_DIR, index_path)
    assert index_path.exists()

    loaded = load_registry_index(index_path)
    assert loaded["Instruments"].keys() == written["Instruments"].keys()


def test_get_instrument_identity_missing_task_returns_empty():
    index = build_registry_index(OFFICIAL_SURVEY_DIR)
    assert get_instrument_identity(index, "does-not-exist") == {}


def test_get_instrument_identity_falls_back_to_variant_id_when_no_version(tmp_path):
    index = {
        "Instruments": {
            "demo": {"TaskName": "demo", "Version": None, "DOI": ""},
        }
    }
    identity = get_instrument_identity(index, "demo", variant_id="short-form")
    assert identity["Version"] == "short-form"
    assert identity["DOI"] is None
