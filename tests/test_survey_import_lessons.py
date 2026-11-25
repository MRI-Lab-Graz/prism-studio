"""What a real longitudinal re-import taught us (2026-11): LimeSurvey response exports.

The response counter `id` is not a participant, a raw Excel/CSV export writes `Group[ITEM]`
headers, its responses must be remembered like an .lsa's, and reports must say what happens.
"""

import csv
import json
import subprocess
import sys

import pandas as pd

from tests.template_fixtures import dump_complete
from tests.test_survey_cli_lsa import PRISM_TOOLS_APP, PROJECT_ROOT, _library, _lsa

EXPORT = ["id", "submitdate", "lastpage", "startlanguage", "seed", "startdate", "Code",
          "W[MTESTSQ001]", "W[MTESTSQ002]", "W[MTESTSQ003]"]
RESPONSES = [
    ["1", "2026-03-01 10:05:00", "2", "en", "111", "2026-03-01 10:00:00", "ABCD", "4", "3", "5"],
    ["2", "2026-03-01 11:05:00", "2", "en", "222", "2026-03-01 11:00:00", "EFGH", "2", "4", "3"],
]


def _export(tmp_path, header=EXPORT, rows=RESPONSES):
    path = tmp_path / "raw_export.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows([header, *rows])
    return path


def _run(tmp_path, source, *extra, library=None):
    return subprocess.run(
        [sys.executable, str(PRISM_TOOLS_APP), "survey", "convert", "--input", str(source),
         "--library", str(library or _library(tmp_path)), "--output", str(tmp_path / "out"),
         "--force", *extra],
        capture_output=True, text=True, encoding="utf-8", cwd=str(PROJECT_ROOT), timeout=120,
    )


def test_response_counter_of_a_raw_export_is_refused_as_participant_id(tmp_path):
    result = _run(tmp_path, _export(tmp_path), "--id-column", "id")

    assert result.returncode != 0
    assert "response number" in result.stdout + result.stderr
    assert "Code" in result.stdout + result.stderr  # says which columns could be meant
    assert not list((tmp_path / "out").glob("sub-*"))


def test_response_counter_of_an_lsa_is_refused_as_participant_id(tmp_path):
    result = _run(tmp_path, _lsa(tmp_path), "--id-column", "id", "--duplicate-handling", "sessions")

    assert result.returncode != 0
    assert "response number" in result.stdout + result.stderr


def test_response_numbers_can_be_mapped_explicitly(tmp_path):
    id_map = tmp_path / "map.tsv"
    id_map.write_text("id\tparticipant_id\n1\tsub-07\n2\tsub-08\n")

    result = _run(tmp_path, _export(tmp_path), "--id-column", "id", "--id-map", str(id_map))

    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(p.name for p in (tmp_path / "out").glob("sub-*")) == ["sub-07", "sub-08"]


def test_an_id_column_in_an_ordinary_table_stays_a_participant_id(tmp_path):
    table = _export(tmp_path, ["id", "MTESTSQ001", "MTESTSQ002", "MTESTSQ003"], [["7", "4", "3", "5"]])

    result = _run(tmp_path, table, "--id-column", "id")

    assert result.returncode == 0, result.stdout + result.stderr
    assert [p.name for p in (tmp_path / "out").glob("sub-*")] == ["sub-7"]


def test_group_item_headers_of_a_raw_export_are_converted(tmp_path):
    result = _run(tmp_path, _export(tmp_path), "--id-column", "Code")

    assert result.returncode == 0, result.stdout + result.stderr
    data = next((tmp_path / "out" / "sub-ABCD").rglob("*_survey.tsv")).read_text(encoding="utf-8")
    assert data.splitlines() == ["MTESTSQ001\tMTESTSQ002\tMTESTSQ003", "4\t3\t5"]


def test_responses_of_a_raw_export_are_remembered(tmp_path):
    result = _run(tmp_path, _export(tmp_path), "--id-column", "Code")

    assert result.returncode == 0, result.stdout + result.stderr
    ledger = json.loads((tmp_path / "out" / "code" / "survey_imports.json").read_text())
    assert ledger["responses"]["sub-ABCD"]["ses-1"][:2] == ["2026-03-01 10:00:00", "111"]


def test_dry_run_names_the_session_it_was_given(tmp_path):
    result = _run(tmp_path, _export(tmp_path), "--id-column", "Code", "--session", "2", "--dry-run")

    assert "Session: 2" in result.stdout, result.stdout + result.stderr
    assert "default ses-1" not in result.stdout


def test_loading_an_id_map_prints_no_debug_output(tmp_path):
    id_map = tmp_path / "map.tsv"
    id_map.write_text("code\tparticipant_id\nABCD\tsub-01\nEFGH\tsub-02\n")

    result = _run(tmp_path, _export(tmp_path), "--id-column", "Code", "--id-map", str(id_map))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "DEBUG" not in result.stdout


def test_empty_cells_are_not_reported_as_rewritten_decimals():
    from src.converters.survey_processing import _trim_padded_numbers

    df = pd.DataFrame({"q1": ["7", float("nan")]})
    templates = {"t": {"json": {"q1": {"DataType": "integer"}}}}

    assert _trim_padded_numbers(df, tasks=["t"], templates=templates, col_to_mapping={}) == []


def test_a_template_whose_file_and_task_name_differ_is_reported(tmp_path):
    library = _library(tmp_path)
    (library / "survey-wellbeing.json").rename(library / "survey-wellbeing2.json")

    result = _run(tmp_path, _export(tmp_path), "--id-column", "Code", "--dry-run", library=library)

    assert "survey-wellbeing2.json" in result.stdout, result.stdout + result.stderr
    assert "task-wellbeing" in result.stdout
