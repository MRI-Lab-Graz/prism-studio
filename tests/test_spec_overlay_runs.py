"""A project's local terms are part of its own validation run and of no other (phase 1, Task 2)."""

import json
import os
import sys
import threading
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from runner import validate_dataset  # noqa: E402
from src.spec_overlay import merge_terms, write_local_terms  # noqa: E402
from src.specification import current_specification, load_specification, official_specification  # noqa: E402

PARENT = {"TermID": "prism:dhea-s", "Level": "analyte", "Label": "DHEA-S", "Aliases": ["dhea_s"], "Description": "d"}
CHILD = {"TermID": "prism:dhea-s.saliva", "Level": "analyte-specimen", "Parent": "prism:dhea-s",
         "SpecimenType": "saliva", "Units": "pg/mL", "MinValue": 0}


def _project(root: Path, overlay: bool) -> Path:
    """A biosample project whose column names the term prism:dhea-s and holds a negative value."""
    root.mkdir(parents=True)
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "T", "BIDSVersion": "1.10.1", "DatasetType": "raw", "Authors": ["A", "B"]}), encoding="utf-8")
    (root / "participants.tsv").write_text("participant_id\nsub-01\n", encoding="utf-8")
    (root / "biosample-saliva_biosample.json").write_text(json.dumps({
        "Technical": {"SpecimenType": "saliva", "CollectionMethod": "passive-drool", "StorageTemperature": -80,
                      "Laboratory": "l", "AssayMethod": "ELISA", "AssayKit": "k", "ProcessingProtocol": "p"},
        "Study": {"BiosampleName": "saliva"},
        "Metadata": {"SchemaVersion": "1.1.0", "CreationDate": "2026-10-23"},
        "sample_id": {"Description": "Tube", "Units": "n/a", "DataType": "string"},
        "dhea_s": {"Term": "prism:dhea-s"},
    }), encoding="utf-8")
    folder = root / "sub-01" / "ses-1" / "biosample"
    folder.mkdir(parents=True)
    (folder / "sub-01_ses-1_biosample-saliva_biosample.tsv").write_text("sample_id\tdhea_s\nS-1\t-1\n", encoding="utf-8")
    if overlay:
        write_local_terms(root, "biosample", [PARENT, CHILD])
    return root


def _messages(project: Path, level="ERROR"):
    issues, _stats = validate_dataset(str(project))
    return [m for lvl, m, *_ in issues if lvl == level]


def test_a_local_term_validates_in_its_own_project(tmp_path):
    messages = _messages(_project(tmp_path / "a", overlay=True))
    assert any("less than MinValue" in m for m in messages)  # inherited from the local child term
    assert not any("not in the term registry" in m for m in messages)


def test_the_next_project_does_not_see_it(tmp_path):
    a, b = _project(tmp_path / "a", True), _project(tmp_path / "b", False)
    assert any("less than MinValue" in m for m in _messages(a))
    after = _messages(b)
    assert not any("less than MinValue" in m for m in after)
    assert any("not in the term registry" in m for m in after)  # B does not know prism:dhea-s


def test_the_same_holds_for_a_run_in_a_worker_thread(tmp_path):
    a, b, found = _project(tmp_path / "a", True), _project(tmp_path / "b", False), []
    worker = threading.Thread(target=lambda: found.extend(_messages(a)))
    worker.start()
    worker.join()
    assert any("less than MinValue" in m for m in found)
    assert not any("less than MinValue" in m for m in _messages(b))
    assert current_specification() is official_specification()


def test_official_terms_win_on_collision(tmp_path):
    (tmp_path / "p").mkdir()
    official = official_specification().terms["biosample"]["cortisol"]
    write_local_terms(tmp_path / "p", "biosample", [{**PARENT, "TermID": "prism:cortisol", "Label": "mine"}])
    spec = load_specification(project_root=tmp_path / "p")
    assert spec.terms["biosample"]["cortisol"] == official
    assert spec.ignored_local == ("prism:cortisol",) and "prism:cortisol" not in spec.local_terms


def test_merge_terms_adds_local_and_ignores_official_stems_and_ids():
    official = {"a": {"TermID": "prism:a"}, "b": {"TermID": "prism:b"}}
    local = {"a": {"TermID": "prism:a", "Label": "x"}, "c": {"TermID": "prism:c"}}
    merged, in_use, ignored = merge_terms(official, local)
    assert list(merged) == ["a", "b", "c"] and merged["a"] is official["a"]
    assert in_use == frozenset({"prism:c"}) and ignored == ("prism:a",)


def test_without_a_project_there_are_no_local_terms():
    spec = load_specification()
    assert spec.local_terms == frozenset() and spec.ignored_local == () and spec.overlay_problems == ()


def test_a_hostile_overlay_never_crashes_a_run(tmp_path):
    project = _project(tmp_path / "p", overlay=False)
    folder = project / "code" / "specification" / "terms" / "biosample"
    folder.mkdir(parents=True)
    for name, content in {"broken.json": "{no", "list.json": "[1]", "types.json": json.dumps({**PARENT, "TermID": "prism:types", "Aliases": 5}),
                          "dhea-s.json": json.dumps(PARENT)}.items():
        (folder / name).write_text(content, encoding="utf-8")
    issues, _stats = validate_dataset(str(project))  # no exception
    assert isinstance(issues, list)
    assert len(load_specification(project_root=project).overlay_problems) == 3


def test_the_wheel_carries_the_two_vendored_scripts(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_validator_wheel

    build_validator_wheel.stage(tmp_path)
    names = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert "prism_validator/scripts/specification/check_terms.py" in names
    assert "prism_validator/scripts/specification/term_proposal.py" in names
    assert "prism_validator/src/spec_overlay.py" in names


# --- notices (phase 1, Task 3) -------------------------------------------------------------------

def _infos(project: Path):
    return _messages(project, "INFO")


def test_a_column_using_a_local_term_says_so_once_with_the_share_command(tmp_path):
    project = _project(tmp_path / "a", overlay=True)
    notes = [m for m in _infos(project) if "uses the local term" in m]
    assert len(notes) == 1
    assert "prism:dhea-s.saliva" in notes[0] and "applies to this project only" in notes[0]
    assert f'spec propose --project "{project}" --term prism:dhea-s.saliva' in notes[0]


def test_official_terms_get_no_local_term_notice(tmp_path):
    project = _project(tmp_path / "a", overlay=False)
    sidecar = project / "biosample-saliva_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["dhea_s"] = {"Term": "cortisol"}
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    assert not [m for m in _infos(project) if "uses the local term" in m]


def test_a_local_term_that_became_official_is_reported_once_per_run(tmp_path):
    project = _project(tmp_path / "a", overlay=False)
    write_local_terms(project, "biosample", [{**PARENT, "TermID": "prism:cortisol", "Label": "mine"}])
    notes = [m for m in _infos(project) if "is now official" in m]
    assert len(notes) == 1 and "prism:cortisol" in notes[0]
    assert f'spec local remove --project "{project}" prism:cortisol' in notes[0]


def test_a_bad_overlay_file_is_a_warning(tmp_path):
    project = _project(tmp_path / "a", overlay=False)
    folder = project / "code" / "specification" / "terms" / "biosample"
    folder.mkdir(parents=True)
    (folder / "broken.json").write_text("{no", encoding="utf-8")
    warnings = _messages(project, "WARNING")
    assert any("ignored local specification file" in m and "broken.json" in m for m in warnings)


def test_the_unknown_metric_notice_offers_to_use_it_here_and_to_share_it(tmp_path):
    project = _project(tmp_path / "b", overlay=False)
    sidecar = project / "biosample-saliva_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["dhea_s"] = {"Description": "d", "Units": "pg/mL"}
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    note = next(m for m in _infos(project) if "is not an official metric" in m)
    assert f'spec local add-term --project "{project}" --data "' in note and "terms propose --data" in note


# --- the official registry also wins over its NAMES (aliases, labels), not only its IDs ---------

def test_a_local_term_cannot_shadow_an_official_alias(tmp_path):
    from src.term_registry import resolve_column

    project = tmp_path / "p"
    project.mkdir()
    write_local_terms(project, "biosample", [
        {"TermID": "prism:cort", "Level": "analyte", "Label": "cort", "Aliases": [], "Description": "d"},
        {"TermID": "prism:cort.saliva", "Level": "analyte-specimen", "Parent": "prism:cort", "SpecimenType": "saliva", "Units": "furlongs"},
        {"TermID": "prism:hydrocortisone", "Level": "analyte", "Label": "mine", "Aliases": [], "Description": "d"},
    ])
    spec = load_specification(project_root=project)
    assert set(spec.ignored_local) == {"prism:cort", "prism:hydrocortisone"}  # cort / hydrocortisone are official aliases
    res = resolve_column(spec.terms["biosample"], "x", {"Term": "cort"}, "saliva")
    assert res.term["TermID"] == "prism:cortisol.saliva" and res.term["Units"] == "nmol/L"
    assert resolve_column(spec.terms["biosample"], "hydrocortisone", {}, "saliva").term["TermID"] == "prism:cortisol"
    assert "prism:cort.saliva" in spec.local_terms  # an orphan child is harmless: nothing reaches it


def test_merge_terms_ignores_a_local_term_whose_label_is_an_official_name():
    official = {"a": {"TermID": "prism:a", "Label": "Alpha", "Aliases": ["al"]}}
    local = {"b": {"TermID": "prism:b", "Label": "alpha", "Aliases": []}, "c": {"TermID": "prism:c", "Label": "c", "Aliases": ["AL"]}}
    _merged, in_use, ignored = merge_terms(official, local)
    assert in_use == frozenset() and ignored == ("prism:b", "prism:c")
