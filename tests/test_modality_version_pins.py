import json
import os
import stat
import sys
from pathlib import Path

import jsonschema
import pytest

from src.modality_versions import (
    ModalityVersionError,
    format_pending_hint,
    freeze_modality,
    pending_updates,
    pin_after_import,
    pin_modalities,
    pin_present_modalities,
    present_modalities,
    read_pins,
    update_modality,
)

REPO = Path(__file__).resolve().parents[1]


def _schema(name, version):
    return {"version": version, "title": name, "type": "object"}


@pytest.fixture
def schema_dir(tmp_path):
    root = tmp_path / "schemas"
    stable = root / "stable"
    stable.mkdir(parents=True)
    (stable / "entities.schema.json").write_text(json.dumps({"modalities": {
        "survey": {"kind": "prism"}, "biometrics": {"kind": "prism"}, "events": {"kind": "prism"}}}))
    for n in ("survey", "biometrics", "events"):
        (stable / f"{n}.schema.json").write_text(json.dumps(_schema(n, "1.1.0")))
    return str(root)


def _project(tmp_path, **extra):
    root = tmp_path / "proj"
    root.mkdir(exist_ok=True)
    (root / "project.json").write_text(json.dumps({"Metadata": {"SchemaVersion": "1.0.0"}, **extra}))
    return root


def _touch(root: Path, rel: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")


def test_present_modalities_by_folder_and_events_by_file(tmp_path, schema_dir):
    root = _project(tmp_path)
    _touch(root, "sub-01/survey/sub-01_task-a_survey.tsv")
    _touch(root, "sub-02/ses-1/biometrics/sub-02_ses-1_task-b_biometrics.tsv")
    _touch(root, "sub-01/func/sub-01_task-a_events.tsv")
    (root / "sub-03" / "biometrics").mkdir(parents=True)  # empty folder does not count
    assert present_modalities(root, schema_dir) == ["survey", "biometrics", "events"]


def test_retired_events_folder_does_not_count_as_events(tmp_path, schema_dir):
    root = _project(tmp_path)
    _touch(root, "sub-01/events/sub-01_task-a_notes.txt")  # events/ is retired; only *_events.* files count
    assert present_modalities(root, schema_dir) == []


def test_pin_present_pins_current_versions_and_never_overwrites(tmp_path, schema_dir):
    root = _project(tmp_path, SchemaVersions={"survey": "1.0.0"})
    _touch(root, "sub-01/survey/sub-01_task-a_survey.tsv")
    _touch(root, "sub-01/biometrics/sub-01_task-b_biometrics.tsv")
    new = pin_present_modalities(root, schema_dir)
    assert new == {"biometrics": "1.1.0"}
    assert read_pins(root)[0] == {"biometrics": "1.1.0", "survey": "1.0.0"}
    assert pin_present_modalities(root, schema_dir) == {}


def test_pinning_keeps_the_rest_of_project_json(tmp_path, schema_dir):
    root = _project(tmp_path, Sessions=[{"id": "ses-1"}])
    _touch(root, "sub-01/survey/sub-01_task-a_survey.tsv")
    pin_present_modalities(root, schema_dir)
    data = json.loads((root / "project.json").read_text())
    assert data["Sessions"] == [{"id": "ses-1"}] and data["SchemaVersions"] == {"survey": "1.1.0"}


def test_no_project_json_means_nothing_is_written(tmp_path, schema_dir):
    root = tmp_path / "bare"
    _touch(root, "sub-01/survey/sub-01_task-a_survey.tsv")
    assert pin_present_modalities(root, schema_dir) == {}
    assert not (root / "project.json").exists()


def test_pin_modalities_by_name_and_unknown_name_error(tmp_path, schema_dir):
    root = _project(tmp_path)
    assert pin_modalities(root, ["survey"], schema_dir) == {"survey": "1.1.0"}
    with pytest.raises(ModalityVersionError):
        pin_modalities(root, ["nope"], schema_dir)


def _bump(schema_dir, name, version):
    (Path(schema_dir) / "stable" / f"{name}.schema.json").write_text(json.dumps(_schema(name, version)))


def test_pending_update_is_told_once_per_new_version(tmp_path, schema_dir):
    root = _project(tmp_path, SchemaVersions={"survey": "1.1.0"})
    assert pending_updates(root, schema_dir) == []
    _bump(schema_dir, "survey", "1.2.0")
    assert pending_updates(root, schema_dir) == [("survey", "1.1.0", "1.2.0")]
    assert freeze_modality(root, "survey", schema_dir) == "1.1.0"
    assert pending_updates(root, schema_dir) == []
    assert read_pins(root)[0]["survey"] == "1.1.0"
    _bump(schema_dir, "survey", "1.3.0")
    assert pending_updates(root, schema_dir) == [("survey", "1.1.0", "1.3.0")]


def test_update_moves_the_pin_and_clears_the_notice(tmp_path, schema_dir):
    root = _project(tmp_path, SchemaVersions={"survey": "1.1.0"})
    _bump(schema_dir, "survey", "1.2.0")
    assert update_modality(root, "survey", schema_dir) == "1.2.0"
    assert read_pins(root)[0]["survey"] == "1.2.0"
    assert pending_updates(root, schema_dir) == []


def test_update_and_freeze_need_a_pin(tmp_path, schema_dir):
    root = _project(tmp_path)
    for fn in (update_modality, freeze_modality):
        with pytest.raises(ModalityVersionError, match="pin"):
            fn(root, "survey", schema_dir)


def test_malformed_pin_values_are_ignored(tmp_path):
    root = _project(tmp_path, SchemaVersions={"survey": "latest", "biometrics": "1.0.0", "x": 3})
    assert read_pins(root)[0] == {"biometrics": "1.0.0"}


def test_pin_after_import_never_raises(tmp_path, capsys, monkeypatch):
    import src.modality_versions as mv

    monkeypatch.setattr(mv, "pin_present_modalities", lambda root: (_ for _ in ()).throw(RuntimeError("boom")))
    pin_after_import(tmp_path)
    assert "boom" in capsys.readouterr().err


def test_hint_lines():
    lines = format_pending_hint([("survey", "1.1.0", "1.2.0")])
    assert "survey" in lines[0] and "1.2.0" in lines[0]
    assert any("modality-version update" in line and "freeze" in line for line in lines)
    assert format_pending_hint([]) == []


def test_project_schema_accepts_the_new_keys_and_rejects_bad_values():
    schema = json.loads((REPO / "app" / "schemas" / "stable" / "project.schema.json").read_text())
    base = {"Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-10-16"},
            "Sessions": [], "TaskDefinitions": {}}
    jsonschema.Draft7Validator(schema).validate({**base, "SchemaVersions": {"survey": "1.1.1"},
                                                  "SchemaVersionsAcknowledged": {"survey": "1.1.1"}})
    assert list(jsonschema.Draft7Validator(schema).iter_errors({**base, "SchemaVersions": {"survey": "latest"}}))
    v = jsonschema.Draft7Validator(schema)
    for bad in (
        {"SchemaVersions": {"Survey": "1.0.0"}},
        {"SchemaVersionsAcknowledged": {"Survey": "1.0.0"}},
        {"SchemaVersions": {"survey": "1.0.0"}, "Bogus": 1},
    ):
        assert list(v.iter_errors({**base, **bad})), bad
    assert schema["version"] == "1.0.0"


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no 0o664 file modes")
def test_pinning_keeps_file_mode(tmp_path, schema_dir):
    root = _project(tmp_path)
    os.chmod(root / "project.json", 0o664)
    pin_modalities(root, ["survey"], schema_dir)
    assert stat.S_IMODE((root / "project.json").stat().st_mode) == 0o664


def test_failed_write_leaves_no_temp_file(tmp_path, schema_dir, monkeypatch):
    root = _project(tmp_path)
    before = (root / "project.json").read_text()

    def boom(*a, **k):
        raise OSError("disk")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        pin_modalities(root, ["survey"], schema_dir)
    assert [p.name for p in root.iterdir()] == ["project.json"]
    assert (root / "project.json").read_text() == before


BAD_NAMES = ["dataset_description", "project", "../stable/biometrics", "nope"]


@pytest.mark.parametrize("bad", BAD_NAMES)
def test_library_rejects_non_modality_names(tmp_path, schema_dir, bad):
    from src.modality_versions import available_versions, current_version, load_modality_schema

    root = _project(tmp_path)
    for call in (
        lambda: pin_modalities(root, [bad], schema_dir),
        lambda: current_version(bad, schema_dir),
        lambda: available_versions(bad, schema_dir),
        lambda: load_modality_schema(bad, "1.0.0", schema_dir),
    ):
        with pytest.raises(ModalityVersionError, match="unknown modality"):
            call()
    for fn in (update_modality, freeze_modality):
        with pytest.raises(ModalityVersionError):
            fn(root, bad, schema_dir)


def test_load_modality_schema_rejects_malformed_version(schema_dir):
    from src.modality_versions import load_modality_schema

    with pytest.raises(ModalityVersionError):
        load_modality_schema("survey", "../../x", schema_dir)


def test_trailing_newline_version_is_rejected(tmp_path):
    from src.modality_versions import parse_overrides

    with pytest.raises(ModalityVersionError):
        parse_overrides(["survey=1.0.0\n"])
    root = _project(tmp_path, SchemaVersions={"survey": "1.0.0\n"})
    assert read_pins(root)[0] == {}


def test_pinning_writes_lf_only(tmp_path, schema_dir):
    root = _project(tmp_path)
    pin_modalities(root, ["survey"], schema_dir)
    assert b"\r" not in (root / "project.json").read_bytes()
