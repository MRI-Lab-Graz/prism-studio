"""A project's schema patch (code/specification/patches/<modality>.json) is part of its own validation run (layer 2, B1)."""

import json
import os
import sys
import threading
from pathlib import Path

import pytest

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


# --- B2: hints and notices ------------------------------------------------------------------------------

def _issues(project: Path, level: str):
    issues, _stats = validate_dataset(str(project))
    return [m for lvl, m, *_ in issues if lvl == level]


def test_the_enum_error_names_the_exact_command(tmp_path):
    project = _project(tmp_path / "p")
    hint = f'python prism_tools.py spec local add-values --project "{project}" --field Technical.SpecimenType --value sweat'
    assert any(hint in m for m in _enum_errors(project))


def test_no_hint_for_a_field_that_cannot_be_patched(tmp_path):
    project = _project(tmp_path / "p")
    sidecar = project / "biosample-sweat_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["Technical"]["SpecimenType"] = "saliva"
    data["Technical"]["CollectionMethod"] = "x" * 100  # not a lowercase value, so no command would be valid
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    assert not any("add-values" in m for m in _issues(project, "ERROR"))


def test_a_project_with_a_local_addition_gets_one_info_naming_the_share_command(tmp_path):
    project = _project(tmp_path / "p", PATCH)
    infos = [m for m in _issues(project, "INFO") if "biosample" in m and "patches" in m]
    assert len(infos) == 1 and f'spec propose --project "{project}" --patch' in infos[0]


def test_an_addition_that_became_official_is_an_info_not_a_warning(tmp_path):
    project = _project(tmp_path / "p", {"operations": [
        {"op": "add_enum_values", "path": "Technical.SpecimenType", "values": ["saliva", "sweat"]}]})
    assert any("saliva" in m and "official" in m and "remove-values" in m for m in _issues(project, "INFO"))
    assert not any("saliva" in m for m in _issues(project, "WARNING"))


def test_a_local_term_on_a_local_specimen_needs_the_patch(tmp_path):
    from src.spec_overlay import OverlayError, add_local_term
    import pytest

    project = _project(tmp_path / "p")
    sidecar = project / "biosample-sweat_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["zonulin"] = {"Description": "Zonulin", "Units": "ng/mL", "DataType": "float"}
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(OverlayError, match="sweat"):
        add_local_term(project, column="zonulin", sidecar_file=sidecar)
    _write(project, PATCH)
    assert add_local_term(project, column="zonulin", sidecar_file=sidecar)["written"]


def test_project_specimens_is_none_for_a_patch_of_a_kind_without_specimen_types(tmp_path):
    from src.spec_overlay import _project_specimens

    _write(tmp_path, {"operations": [{"op": "add_enum_values", "path": "Technical.StimulusType", "values": ["interview"]}]}, "survey")
    assert _project_specimens(tmp_path, "survey") is None


def _enum(schema, field):
    node = schema
    for part in field.split("."):
        node = node["properties"][part]
    return node["enum"]


def test_a_survey_patch_validates_its_new_value(tmp_path):
    from src.spec_overlay import add_local_values

    project = _project(tmp_path / "p")
    add_local_values(project, "Study.LicenseID", ["cc-by-nc-local"], modality="survey")
    spec = load_specification(project_root=project)
    assert "cc-by-nc-local" in _enum(spec.schemas["survey"], "Study.LicenseID") and "survey" in spec.local_patches


def test_patch_files_that_are_not_a_kind_of_data_are_skipped_and_reported(tmp_path):
    for name in ("Survey.json", "unknown.json", "x.y.json"):
        _write(tmp_path, {"operations": []}, name[:-5])
    spec = load_specification(project_root=tmp_path)
    assert {p.split(":")[0] for p in spec.overlay_problems} >= {"patches/Survey.json", "patches/unknown.json", "patches/x.y.json"}


def test_a_survey_patch_does_not_leak_into_the_next_project(tmp_path):
    from src.spec_overlay import add_local_values

    a, b = _project(tmp_path / "a"), _project(tmp_path / "b")
    add_local_values(a, "Study.LicenseID", ["cc-by-nc-local"], modality="survey")
    load_specification(project_root=a)
    assert "cc-by-nc-local" not in _enum(load_specification(project_root=b).schemas["survey"], "Study.LicenseID")


def test_a_patch_that_does_not_fit_the_runs_schema_is_a_problem_not_a_crash(tmp_path):
    _write(tmp_path, {"operations": [{"op": "add_enum_values", "path": "Study.NoSuchField", "values": ["x"]}]}, "survey")
    assert any("survey.json" in p for p in load_specification(project_root=tmp_path).overlay_problems)


def test_add_values_refuses_an_unknown_modality_and_a_field_it_does_not_list(tmp_path):
    from src.spec_overlay import OverlayError, add_local_values

    with pytest.raises(OverlayError, match="nomodality"):
        add_local_values(tmp_path, "Study.LicenseID", ["x-y"], modality="nomodality")
    with pytest.raises(OverlayError, match="Study.NoSuchField"):
        add_local_values(tmp_path, "Study.NoSuchField", ["x-y"], modality="survey")


@pytest.mark.parametrize("modality", ["../../../../outside", "../x", "Survey", "unknown"])
def test_add_and_remove_values_refuse_a_modality_that_is_not_a_kind_of_data(tmp_path, modality):
    """A caller-supplied modality names a file: `../..` must never reach outside the project (remove-values deleted it)."""
    from src.spec_overlay import OverlayError, add_local_values, remove_local_values

    project = tmp_path / "a" / "b" / "c" / "p"
    patches = project / "code" / "specification" / "patches"
    patches.mkdir(parents=True)
    target = Path(os.path.normpath(patches / f"{modality}.json"))  # the file a missing check would touch
    target.write_text(json.dumps({"operations": [
        {"op": "add_enum_values", "path": "Study.LicenseID", "values": ["x-y"]}]}), encoding="utf-8")
    with pytest.raises(OverlayError, match="not a kind of data"):
        remove_local_values(project, "Study.LicenseID", ["x-y"], modality=modality)
    with pytest.raises(OverlayError, match="not a kind of data"):
        add_local_values(project, "Study.LicenseID", ["z-z"], modality=modality)
    assert json.loads(target.read_text(encoding="utf-8"))["operations"][0]["values"] == ["x-y"]


def test_the_share_and_remove_hints_of_a_survey_addition_name_the_modality(tmp_path):
    project = _project(tmp_path / "p")
    _write(project, {"operations": [{"op": "add_enum_values", "path": "Technical.Respondent", "values": ["sibling", "parent"]}]}, "survey")
    infos = _issues(project, "INFO")
    share = [m for m in infos if "patches/survey.json" in m]
    assert len(share) == 1 and f'spec propose --project "{project}" --patch --modality survey' in share[0]
    assert any("remove-values" in m and "--modality survey" in m for m in infos)


def test_list_all_local_items_covers_every_kind_of_data_with_a_patch(tmp_path):
    from src.spec_overlay import add_local_values, list_all_local_items

    project = _project(tmp_path / "p")
    assert {i["modality"] for i in list_all_local_items(project)} <= {"biosample"}
    add_local_values(project, "Technical.SpecimenType", ["sweat2"], modality="biosample")
    add_local_values(project, "Study.LicenseID", ["cc-by-nc-local"], modality="survey")
    pairs = {(i["modality"], i["layer"]) for i in list_all_local_items(project)}
    assert {("biosample", 2), ("survey", 2)} <= pairs and {m for m, _ in pairs} == {"biosample", "survey"}
