"""src/spec_overlay.py: a project's own, not yet official terms (code/specification/terms/<modality>/)."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.spec_overlay import (  # noqa: E402
    OverlayError, load_local_terms, overlay_root, remove_local_terms, write_local_terms,
)

PARENT = {"TermID": "prism:dhea-s", "Level": "analyte", "Label": "DHEA-S", "Aliases": ["dhea_s"], "Description": "d"}
CHILD = {"TermID": "prism:dhea-s.saliva", "Level": "analyte-specimen", "Parent": "prism:dhea-s",
         "SpecimenType": "saliva", "Units": "pg/mL", "MinValue": 0}


def _folder(project: Path) -> Path:
    folder = project / "code" / "specification" / "terms" / "biosample"
    folder.mkdir(parents=True)
    return folder


def _put(folder: Path, name: str, content) -> None:
    (folder / name).write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")


def test_overlay_lives_in_the_code_folder(tmp_path):
    assert overlay_root(tmp_path) == tmp_path / "code" / "specification"


def test_load_local_terms_reads_valid_files(tmp_path):
    folder = _folder(tmp_path)
    _put(folder, "dhea-s.json", PARENT)
    _put(folder, "dhea-s.saliva.json", CHILD)
    terms, problems = load_local_terms(tmp_path)
    assert problems == [] and terms == {"dhea-s": PARENT, "dhea-s.saliva": CHILD}


def test_missing_overlay_is_empty(tmp_path):
    assert load_local_terms(tmp_path) == ({}, [])


@pytest.mark.parametrize(
    "name,content",
    [
        ("broken.json", "{not json"),
        ("list.json", "[1, 2]"),
        ("alias.json", {**PARENT, "TermID": "prism:alias", "Aliases": 5}),
        ("wrongstem.json", PARENT),  # TermID local part is dhea-s
        ("newline.json", {**PARENT, "TermID": "prism:newline\n"}),
        ("prefix.json", {**PARENT, "TermID": "bids:prefix"}),
    ],
)
def test_load_skips_and_reports_bad_files(tmp_path, name, content):
    folder = _folder(tmp_path)
    _put(folder, name, content)
    _put(folder, "dhea-s.json", PARENT)
    terms, problems = load_local_terms(tmp_path)
    assert list(terms) == ["dhea-s"] and len(problems) >= 1 and name in problems[0]


def test_write_creates_one_file_per_term_without_status(tmp_path):
    written = write_local_terms(tmp_path, "biosample", [PARENT, CHILD])
    assert sorted(p.name for p in written) == ["dhea-s.json", "dhea-s.saliva.json"]
    assert "Status" not in json.loads(written[0].read_text(encoding="utf-8"))
    assert load_local_terms(tmp_path) == ({"dhea-s": PARENT, "dhea-s.saliva": CHILD}, [])


@pytest.mark.parametrize("tid", ["prism:../x", "prism:a\n", "prism:A", "prism:a/b", "x", "bids:x"])
def test_write_refuses_a_bad_local_part(tmp_path, tid):
    with pytest.raises(OverlayError):
        write_local_terms(tmp_path, "biosample", [{**PARENT, "TermID": tid}])
    assert not (tmp_path / "code").exists()


def test_remove_parent_removes_children(tmp_path):
    write_local_terms(tmp_path, "biosample", [PARENT, CHILD])
    removed = remove_local_terms(tmp_path, "biosample", "prism:dhea-s")
    assert sorted(p.name for p in removed) == ["dhea-s.json", "dhea-s.saliva.json"]
    assert load_local_terms(tmp_path) == ({}, [])


def test_remove_a_child_keeps_the_parent(tmp_path):
    write_local_terms(tmp_path, "biosample", [PARENT, CHILD])
    remove_local_terms(tmp_path, "biosample", "prism:dhea-s.saliva")
    assert list(load_local_terms(tmp_path)[0]) == ["dhea-s"]


def test_remove_unknown_id_is_an_error(tmp_path):
    with pytest.raises(OverlayError, match="no local term"):
        remove_local_terms(tmp_path, "biosample", "prism:nope")


@pytest.mark.parametrize("tid", ["prism:../outside", "../outside", "prism:a/b", "prism:x\n"])
def test_remove_cannot_leave_the_overlay_folder(tmp_path, tid):
    (tmp_path / "outside.json").write_text("{}", encoding="utf-8")
    with pytest.raises(OverlayError):
        remove_local_terms(tmp_path, "biosample", tid)
    assert (tmp_path / "outside.json").exists()


# --- review fixes: missing scripts, deep JSON, symlinks, Status ---------------------------------

import importlib

import src.spec_overlay as overlay_module


@pytest.fixture
def no_scripts(tmp_path, monkeypatch):
    """The validator image without scripts/specification: the scripts directory points at an empty folder."""
    monkeypatch.setattr(overlay_module, "specification_scripts_dir", lambda: tmp_path / "nowhere")
    overlay_module._vendored.cache_clear()
    yield
    overlay_module._vendored.cache_clear()


def test_missing_vendored_scripts_degrade_to_a_message_not_an_exception(tmp_path, no_scripts):
    project = tmp_path / "p"
    _put(_folder(project), "dhea-s.json", PARENT)
    terms, problems = load_local_terms(project)
    assert terms == {} and len(problems) == 1 and "scripts" in problems[0]


def test_missing_vendored_scripts_are_not_noticed_without_an_overlay(tmp_path, no_scripts):
    assert load_local_terms(tmp_path) == ({}, [])


def test_deeply_nested_json_is_a_skipped_file_not_a_crash(tmp_path):
    folder = _folder(tmp_path)
    (folder / "deep.json").write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
    _put(folder, "dhea-s.json", PARENT)
    terms, problems = load_local_terms(tmp_path)
    assert list(terms) == ["dhea-s"] and len(problems) == 1 and "deep.json" in problems[0]
    assert remove_local_terms(tmp_path, "biosample", "prism:dhea-s")  # scanning for children survives it too


def test_a_local_file_may_not_set_status(tmp_path):
    folder = _folder(tmp_path)
    _put(folder, "dhea-s.json", {**PARENT, "Status": "deprecated", "ReplacedBy": "prism:cortisol"})
    terms, problems = load_local_terms(tmp_path)
    assert terms == {} and "Status" in problems[0]


needs_symlinks = pytest.mark.skipif(os.name == "nt", reason="symbolic links need extra rights on Windows")


@needs_symlinks
def test_a_symlinked_file_is_never_written_through(tmp_path):
    victim = tmp_path / "victim.rc"
    victim.write_text("keep me\n", encoding="utf-8")
    (_folder(tmp_path / "p") / "dhea-s.json").symlink_to(victim)
    with pytest.raises(OverlayError, match="already exists"):
        write_local_terms(tmp_path / "p", "biosample", [PARENT])
    assert victim.read_text(encoding="utf-8") == "keep me\n"


@needs_symlinks
def test_a_symlinked_specification_folder_is_refused_for_writing_and_removing(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "terms" / "biosample").mkdir(parents=True)
    (elsewhere / "terms" / "biosample" / "dhea-s.json").write_text(json.dumps(PARENT), encoding="utf-8")
    project = tmp_path / "p"
    (project / "code").mkdir(parents=True)
    (project / "code" / "specification").symlink_to(elsewhere)
    with pytest.raises(OverlayError, match="symbolic link"):
        write_local_terms(project, "biosample", [PARENT])
    with pytest.raises(OverlayError, match="symbolic link"):
        remove_local_terms(project, "biosample", "prism:dhea-s")
    assert [p.name for p in (elsewhere / "terms" / "biosample").iterdir()] == ["dhea-s.json"]


def test_an_existing_file_is_never_overwritten(tmp_path):
    folder = _folder(tmp_path)
    _put(folder, "dhea-s.json", "{hand edited, typo")
    with pytest.raises(OverlayError, match="already exists"):
        write_local_terms(tmp_path, "biosample", [PARENT, CHILD])
    assert (folder / "dhea-s.json").read_text(encoding="utf-8") == "{hand edited, typo"
    assert not (folder / "dhea-s.saliva.json").exists()  # nothing was written before the check
