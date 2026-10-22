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
