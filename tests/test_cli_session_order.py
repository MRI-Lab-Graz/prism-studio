"""prism_tools.py session-order, and sessions review in a content project."""

import json
import sys

import pandas as pd
import pytest

from src.session_order import load_session_order


def run_cli(*argv):
    from src.cli.entrypoint import main

    old = sys.argv
    sys.argv = ["prism_tools.py", *argv]
    try:
        main()
    finally:
        sys.argv = old


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.json").write_text(
        json.dumps(
            {
                "Basics": {"Name": "Sleep", "Authors": ["A. Author"], "Keywords": ["sleep"]},
                "StudyDesign": {"Timepoints": "multiple", "SessionLabels": "content"},
            }
        )
    )
    return root


def test_set_then_show_round_trips(proj, capsys):
    run_cli("session-order", "set", "--project", str(proj), "--participant", "P01", "--number", "1", "--session", "sleepdep")
    run_cli("session-order", "set", "--project", str(proj), "--participant", "P01", "--number", "2", "--session", "rested")
    capsys.readouterr()

    run_cli("session-order", "show", "--project", str(proj), "--json")

    assert json.loads(capsys.readouterr().out) == {
        "session_labels": "content",
        "order": {"P01": {"1": "sleepdep", "2": "rested"}},
    }


def test_import_reads_a_prepared_file(proj, tmp_path):
    prepared = tmp_path / "order.csv"
    pd.DataFrame(
        {"participant_id": ["P01", "P02"], "session_number": [1, 1], "session": ["a", "b"]}
    ).to_csv(prepared, index=False)

    run_cli("session-order", "import", "--project", str(proj), "--file", str(prepared))

    assert load_session_order(proj) == {"P01": {"1": "a"}, "P02": {"1": "b"}}


def test_unset_removes_a_participant(proj):
    run_cli("session-order", "set", "--project", str(proj), "--participant", "P01", "--number", "1", "--session", "a")

    run_cli("session-order", "unset", "--project", str(proj), "--participant", "P01")

    assert load_session_order(proj) == {}


def test_an_invalid_name_exits_with_code_2(proj, capsys):
    with pytest.raises(SystemExit) as info:
        run_cli("session-order", "set", "--project", str(proj), "--participant", "P01", "--number", "1", "--session", "sleep dep")
    assert info.value.code == 2
    assert "letters and digits" in capsys.readouterr().out


def test_sessions_review_shows_condition_names_and_the_mismatch(proj, tmp_path, capsys):
    run_cli("session-order", "set", "--project", str(proj), "--participant", "P01", "--number", "1", "--session", "sleepdep")
    run_cli("session-order", "set", "--project", str(proj), "--participant", "P01", "--number", "2", "--session", "rested")
    source = tmp_path / "in.csv"
    pd.DataFrame(
        [
            {"id": "1", "token": "P01", "startdate": "2026-01-05 10:00:00", "submitdate": "x"},
            {"id": "2", "token": "P01", "startdate": "2026-02-05 10:00:00", "submitdate": "x"},
            {"id": "3", "token": "P02", "startdate": "2026-01-06 10:00:00", "submitdate": "x"},
        ]
    ).to_csv(source, index=False)
    capsys.readouterr()

    run_cli("sessions", "review", "--input", str(source), "--id-column", "token", "--project", str(proj), "--json")

    payload = json.loads(capsys.readouterr().out)
    by_response = {r["response_id"]: r for r in payload["rows"]}
    assert by_response["1"]["session"] == "sleepdep"
    assert by_response["2"]["session"] == "rested"
    assert by_response["3"]["session"] is None
    assert by_response["3"]["reason"] == "not in session order"
    assert any("P02: not in the session order" in w for w in payload["warnings"])
