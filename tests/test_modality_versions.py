import json
from pathlib import Path

import pytest

from src.modality_versions import (
    ModalityVersionError,
    available_versions,
    current_version,
    load_modality_schema,
    modality_names,
    parse_overrides,
    resolve_modality_versions,
)


def _schema(name: str, version: str) -> dict:
    return {"$id": f"https://prism.org/schemas/{name}/v{version}", "version": version,
            "title": name, "type": "object", "properties": {"Metadata": {"type": "object"}}}


@pytest.fixture
def schema_dir(tmp_path: Path) -> str:
    stable = tmp_path / "stable"
    stable.mkdir()
    (stable / "entities.schema.json").write_text(json.dumps({"modalities": {
        "survey": {"kind": "prism"}, "physio": {"kind": "prism"}, "anat": {"kind": "bidsPassthrough"}}}))
    (stable / "survey.schema.json").write_text(json.dumps(_schema("survey", "1.2.0")))
    (stable / "physio.schema.json").write_text(json.dumps(_schema("physio", "1.0.0")))
    archive = tmp_path / "archive" / "survey"
    archive.mkdir(parents=True)
    for v in ("1.0.0", "1.1.0", "1.10.0"):
        (archive / f"{v}.schema.json").write_text(json.dumps(_schema("survey", v)))
    return str(tmp_path)


def test_names_are_modalities_that_have_a_stable_schema(schema_dir):
    assert modality_names(schema_dir) == ["survey", "physio"]  # anat has no schema file




def test_unknown_modality_lists_the_known_ones(schema_dir):
    with pytest.raises(ModalityVersionError, match="survey, physio"):
        current_version("nope", schema_dir)


def test_available_versions_are_sorted_by_semver_not_text(schema_dir):
    assert available_versions("survey", schema_dir) == ["1.0.0", "1.1.0", "1.2.0", "1.10.0"]
    assert available_versions("physio", schema_dir) == ["1.0.0"]


def test_load_current_and_archived_versions(schema_dir):
    assert load_modality_schema("survey", "1.2.0", schema_dir)["_validator_info"]["schema_version"] == "1.2.0"
    old = load_modality_schema("survey", "1.1.0", schema_dir)
    assert old["version"] == "1.1.0"
    assert old["_validator_info"]["schema_version"] == "1.1.0"
    assert old["_validator_info"]["modality"] == "survey"


def test_unknown_version_is_an_error_listing_what_exists(schema_dir):
    with pytest.raises(ModalityVersionError) as exc:
        load_modality_schema("survey", "9.9.9", schema_dir)
    assert "1.0.0" in str(exc.value) and "1.2.0" in str(exc.value)


def test_parse_overrides():
    assert parse_overrides(["survey=1.0.3", "physio=2.0.0"]) == {"survey": "1.0.3", "physio": "2.0.0"}


@pytest.mark.parametrize("bad", ["survey", "survey=1.0", "=1.0.0", "survey=v1.0.0", "survey=1.0.0=2"])
def test_malformed_overrides_are_errors(bad):
    with pytest.raises(ModalityVersionError, match="NAME=X.Y.Z"):
        parse_overrides([bad])


def test_resolution_precedence_and_sources(schema_dir):
    versions, sources = resolve_modality_versions(
        pins={"survey": "1.1.0", "physio": "1.0.0"}, overrides={"survey": "1.0.0"}, schema_dir=schema_dir)
    assert versions == {"survey": "1.0.0", "physio": "1.0.0"}
    assert sources == {"survey": "cli", "physio": "project.json"}
    versions, sources = resolve_modality_versions(schema_dir=schema_dir)
    assert versions == {"survey": "1.2.0", "physio": "1.0.0"}
    assert set(sources.values()) == {"latest"}


def test_pin_for_a_modality_that_no_longer_exists_is_ignored(schema_dir):
    versions, _ = resolve_modality_versions(pins={"gone": "1.0.0"}, schema_dir=schema_dir)
    assert "gone" not in versions


def test_override_for_an_unknown_modality_is_an_error(schema_dir):
    with pytest.raises(ModalityVersionError, match="survey, physio"):
        resolve_modality_versions(overrides={"nope": "1.0.0"}, schema_dir=schema_dir)
