"""Biosample import uses the project's code maps (invented codes only)."""

import json

import pytest
from openpyxl import load_workbook

from src.biosample_import import import_biosample
from src.biosample_template import write_biosample_template

PROJECT = {"StudyDesign": {"Timepoints": "multiple"}}


def _setup(tmp_path, rows, maps):
    project = tmp_path / "p"
    (project / "code").mkdir(parents=True)
    (project / "project.json").write_text(json.dumps(PROJECT))
    (project / "code" / "session_map.json").write_text(json.dumps({"T1": "1", "T2": "2"}))
    for name, entries in maps.items():
        (project / "code" / name).write_text("code\tparticipant_id\n" + "".join(f"{c}\t{p}\n" for c, p in entries))
    book = tmp_path / "filled.xlsx"
    write_biosample_template(book)
    wb = load_workbook(book)
    for code, session in rows:
        wb["data"].append([code, session, "hormones", None, "s1", "08:30", "cortisol", 1, "nmol/L", None])
    wb["panels"].append(["hormones"])
    wb.save(book)
    return book, project


def _written(project):
    return sorted(p.relative_to(project).as_posix() for p in project.glob("sub-*/ses-*/biosample/*.tsv"))


GENERAL = {"biosample_code_map.tsv": [("QQAA", "sub-001")]}


def test_general_and_session_maps_and_no_code_in_files_or_report(tmp_path):
    maps = {**GENERAL, "biosample_ses-2_code_map.tsv": [("QQAA", "sub-002")]}
    book, project = _setup(tmp_path, [("qqaa", "T1"), ("qqaa", "T2")], maps)
    res = import_biosample(book, project, specimen="serum")
    assert not res.errors, res.errors
    assert [p.split("/")[0] + "/" + p.split("/")[1] for p in _written(project)] == ["sub-001/ses-1", "sub-002/ses-2"]
    assert "Applied code map biosample_code_map.tsv: 1 code(s)." in res.warnings
    assert "qqaa" not in "\n".join(res.warnings + res.written).lower()


@pytest.mark.parametrize("dry_run", [False, True])
def test_every_unlisted_row_is_reported_and_nothing_is_written(tmp_path, dry_run):
    book, project = _setup(tmp_path, [("QQAA", "T1"), ("QQBB", "T1"), ("QQCC", "T2")], GENERAL)
    res = import_biosample(book, project, specimen="serum", dry_run=dry_run)
    missing = [e for e in res.errors if "missing in the mapping" in e]
    assert [e.split(": ", 1)[1] for e in missing] == [
        "ID mapping incomplete: 1 IDs from data are missing in the mapping: QQBB.",
        "ID mapping incomplete: 1 IDs from data are missing in the mapping: QQCC.",
    ]
    assert all(e.startswith("data row ") for e in missing)
    assert not res.written and _written(project) == []


def test_an_unfilled_map_stops(tmp_path):
    book, project = _setup(tmp_path, [("QQAA", "T1")], {"biosample_code_map.tsv": []})
    res = import_biosample(book, project, specimen="serum")
    assert res.errors and _written(project) == []


def test_a_broken_map_is_an_error_not_a_crash(tmp_path):
    book, project = _setup(tmp_path, [("QQAA", "T1")], {})
    (project / "code" / "biosample_code_map.tsv").write_text("wrong\theader\n")
    res = import_biosample(book, project, specimen="serum")
    assert "biosample_code_map.tsv" in res.errors[0] and _written(project) == []
