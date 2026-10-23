"""A project's schema patch (code/specification/patches/<modality>.json) is part of its own validation run (layer 2, B1)."""

import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from runner import validate_dataset  # noqa: E402
from src.spec_overlay import load_local_patches  # noqa: E402
from src.specification import current_specification, load_specification, official_specification  # noqa: E402

PATCH = {"operations": [{"op": "add_enum_values", "path": "Technical.SpecimenType", "values": ["sweat"]}]}


def _write(root: Path, patch, modality="biosample") -> Path:
    path = root / "code" / "specification" / "patches" / f"{modality}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(patch if isinstance(patch, str) else json.dumps(patch), encoding="utf-8")
    return path


def _project(root: Path, patch=None) -> Path:
    root.mkdir(parents=True)
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "T", "BIDSVersion": "1.10.1", "DatasetType": "raw", "Authors": ["A", "B"]}), encoding="utf-8")
    (root / "participants.tsv").write_text("participant_id\nsub-01\n", encoding="utf-8")
    (root / "biosample-sweat_biosample.json").write_text(json.dumps({
        "Technical": {"SpecimenType": "sweat", "CollectionMethod": "swab", "StorageTemperature": -80,
                      "Laboratory": "l", "AssayMethod": "ELISA", "AssayKit": "k", "ProcessingProtocol": "p"},
        "Study": {"BiosampleName": "sweat"},
        "Metadata": {"SchemaVersion": "1.1.0", "CreationDate": "2026-10-23"},
        "sample_id": {"Description": "Tube", "Units": "n/a", "DataType": "string"},
    }), encoding="utf-8")
    folder = root / "sub-01" / "ses-1" / "biosample"
    folder.mkdir(parents=True)
    (folder / "sub-01_ses-1_biosample-sweat_biosample.tsv").write_text("sample_id\nS-1\n", encoding="utf-8")
    if patch:
        _write(root, patch)
    return root


def _enum_errors(project: Path):
    issues, _stats = validate_dataset(str(project))
    return [m for lvl, m, *_ in issues if lvl == "ERROR" and "sweat" in m]


def test_a_valid_patch_is_loaded(tmp_path):
    _write(tmp_path, PATCH)
    patch, problems = load_local_patches(tmp_path)
    assert patch == PATCH and problems == []


def test_no_patch_is_not_a_problem(tmp_path):
    assert load_local_patches(tmp_path) == (None, [])


def test_hostile_files_are_skipped_and_reported(tmp_path):
    for content in ("{not json", "[]", json.dumps({"operations": [{"op": "drop", "path": "x"}]}),
                    json.dumps({"operations": [{"op": "add_enum_values", "path": "../../etc", "values": ["x"]}]}),
                    "[" * 100000):
        _write(tmp_path, content)
        patch, problems = load_local_patches(tmp_path)
        assert patch is None and len(problems) == 1


def test_already_official_values_are_dropped_and_reported(tmp_path):
    _write(tmp_path, {"operations": [{"op": "add_enum_values", "path": "Technical.SpecimenType", "values": ["saliva", "sweat"]}]})
    patch, problems = load_local_patches(tmp_path)
    assert patch["operations"][0]["values"] == ["sweat"]
    assert any("saliva" in p and "official" in p for p in problems)
    _write(tmp_path, {"operations": [{"op": "add_enum_values", "path": "Technical.SpecimenType", "values": ["saliva"]}]})
    assert load_local_patches(tmp_path)[0] is None  # nothing left to add


def test_a_symlinked_folder_is_not_followed(tmp_path):
    outside = tmp_path / "outside"
    _write(outside.parent / "outside_project", PATCH)
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "specification").symlink_to(outside.parent / "outside_project" / "code" / "specification")
    assert load_local_patches(tmp_path)[0] is None


def test_the_specification_carries_the_patched_schema_and_the_official_one_is_untouched(tmp_path):
    _write(tmp_path, PATCH)
    spec = load_specification(project_root=tmp_path)
    enum = lambda s: s.schemas["biosample"]["properties"]["Technical"]["properties"]["SpecimenType"]["enum"]
    assert "sweat" in enum(spec) and spec.local_patches == ("biosample",)
    assert "sweat" not in enum(official_specification()) and official_specification().local_patches == ()


def test_a_bad_patch_is_an_overlay_problem(tmp_path):
    _write(tmp_path, "{nope")
    spec = load_specification(project_root=tmp_path)
    assert spec.local_patches == () and any("biosample.json" in p for p in spec.overlay_problems)


def test_the_sweat_project_validates_with_its_patch_and_fails_without(tmp_path):
    assert _enum_errors(_project(tmp_path / "with", PATCH)) == []
    assert _enum_errors(_project(tmp_path / "without"))


def test_the_next_project_does_not_see_the_patch_even_in_a_thread(tmp_path):
    a, b = _project(tmp_path / "a", PATCH), _project(tmp_path / "b")
    assert _enum_errors(a) == [] and _enum_errors(b)
    seen = []
    thread = threading.Thread(target=lambda: seen.append(_enum_errors(b)))
    thread.start(); thread.join()
    assert seen[0]
    assert current_specification() is official_specification()


def test_missing_scripts_give_a_message_not_a_crash(tmp_path, monkeypatch):
    import src.spec_overlay as overlay

    def missing(name):
        raise FileNotFoundError(name)

    monkeypatch.setattr(overlay, "_vendored", missing)
    _write(tmp_path, PATCH)
    patch, problems = load_local_patches(tmp_path)
    assert patch is None and len(problems) == 1
