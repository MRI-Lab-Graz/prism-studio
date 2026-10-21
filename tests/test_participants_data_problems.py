"""Problems in a participants source table that the preview reports before anything is written."""

import pandas as pd

from src.participant_data_checks import find_participant_data_problems


def _df(rows, columns=("participant_id", "age", "iq")):
    return pd.DataFrame(rows, columns=list(columns))


def _problems(rows, **kw):
    return find_participant_data_problems(_df(rows, **kw), "participant_id")


def test_clean_table_has_no_problems():
    assert _problems([("P1", "21", "100"), ("P2", "30", "99")]) == {"warnings": [], "errors": []}


def test_rows_without_an_id_are_a_warning_naming_the_rows():
    out = _problems([("P1", "21", "100"), ("", "22", "101"), (None, "23", "102"), ("n/a", "24", "103")])
    (warning,) = out["warnings"]
    assert "3 row(s)" in warning and "no participant ID" in warning and "2, 3, 4" in warning
    assert out["errors"] == []


def test_different_ids_that_become_the_same_prism_id_are_a_warning():
    out = _problems([("P-1", "21", "1"), ("P 1", "22", "2"), ("P2", "23", "3"), ("P2", "23", "3")])
    (warning,) = [w for w in out["warnings"] if "become the same participant" in w]
    assert "sub-P1" in warning and "P-1" in warning and "P 1" in warning
    assert "sub-P2" not in " ".join(out["warnings"])  # the same typed ID twice is a repeated row, not a collision


def test_sub_prefix_and_bare_label_are_the_same_id_not_a_collision_warning_of_cleaning():
    # "sub-P1" and "P1" differ as typed and give the same PRISM ID: that is a collision too
    (warning,) = _problems([("sub-P1", "21", "1"), ("P1", "22", "2")])["warnings"]  # no cleaning note: nothing was removed
    assert "sub-P1" in warning


def test_text_in_a_numeric_column_is_an_error_per_value():
    out = _problems([("P1", "21", "100"), ("P2", "twenty", "99"), ("P3", "30", "n/a"), ("P4", "31", "abc"), ("P5", "32", "98")])
    assert len(out["errors"]) == 2
    assert any("age" in e and "P2" in e and "twenty" in e for e in out["errors"])
    assert any("iq" in e and "P4" in e for e in out["errors"])


def test_decimal_comma_counts_as_a_number():
    assert _problems([("P1", "21,5", "100,2"), ("P2", "30", "99")])["errors"] == []


def test_mostly_text_column_is_not_a_numeric_column():
    out = _problems([("P1", "a", "x"), ("P2", "b", "y"), ("P3", "c", "1")])
    assert out["errors"] == []


def test_age_outside_a_human_range_is_an_error():
    out = _problems([("P1", "21", "1"), ("P2", "-5", "1"), ("P3", "200", "1"), ("P4", "0", "1"), ("P5", "120", "1")])
    (error,) = out["errors"]  # one message per column
    assert "2 age(s)" in error and "P2: -5" in error and "P3: 200" in error


def test_only_a_column_called_age_gets_the_age_range():
    out = _problems([("P1", "500", "-3")], columns=("participant_id", "language_score", "iq"))
    assert out["errors"] == []


def test_many_problems_are_summarised_with_examples():
    rows = [(f"P{i}", "x", "1") for i in range(1, 3)] + [(f"Q{i}", str(i), "1") for i in range(14)] + [(f"R{i}", "bad", "1") for i in range(8)]
    (error,) = [e for e in _problems(rows)["errors"] if "age" in e] or [None]
    assert error and "10 value(s)" in error and "more" in error


def test_only_the_asked_columns_are_checked():
    df = _df([("P1", "twenty", "abc")])
    assert find_participant_data_problems(df, "participant_id", columns=["iq"])["errors"] == []


def test_convert_refuses_a_source_with_text_in_a_numeric_column(tmp_path):
    import json

    from src.participants_converter import ParticipantsConverter

    src = tmp_path / "in.csv"
    src.write_text("participant_id,age\n" + "".join(f"P{i},{20 + i}\n" for i in range(5)) + "P9,twenty\n")
    mapping = {"version": "1.0", "mappings": {
        "participant_id": {"source_column": "participant_id", "standard_variable": "participant_id", "type": "string"},
        "age": {"source_column": "age", "standard_variable": "age", "type": "string"}}}
    out = tmp_path / "participants.tsv"
    ok, _, messages = ParticipantsConverter(tmp_path).convert_participant_data(
        src, mapping, output_file=out, reject_conflicting_repeats=True)
    assert not ok and not out.exists()
    assert any("not numbers" in m for m in messages)


CSV_WITH_PROBLEMS = "participant_id,age\nP1,21\nP-2,22\nP 2,23\n,24\nP5,twenty\nP6,200\nP7,30\nP8,31\n"


def test_the_gui_preview_reports_them_in_the_summary(tmp_path):
    import io

    from tests.test_participants_session_map_preview import make_client

    client = make_client(tmp_path, {})
    body = client.post(
        "/api/participants-preview",
        data={"mode": "file", "file": (io.BytesIO(CSV_WITH_PROBLEMS.encode()), "d.csv"), "id_column": "participant_id"},
        content_type="multipart/form-data",
    ).get_json()
    warnings = " ".join(body["data_warnings"])
    assert "no participant ID" in warnings and "sub-P2" in warnings
    assert any("not numbers" in e for e in body["data_errors"])
    assert any("outside 0-120" in e for e in body["data_errors"])


def test_the_cli_preview_reports_them_too(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    src = tmp_path / "d.csv"
    src.write_text(CSV_WITH_PROBLEMS)
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "prism_tools.py"), "participants", "preview", "--input", str(src),
         "--project", str(tmp_path), "--json"],
        capture_output=True, text=True, env={**__import__("os").environ, "PRISM_SKIP_VENV_CHECK": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert len(payload["data_errors"]) == 2 and payload["data_warnings"]


def test_cleaned_ids_are_reported_but_a_added_prefix_is_not():
    out = _problems([("P 1", "21", "1"), ("P2", "22", "2"), ("sub-P3", "23", "3")])
    (warning,) = out["warnings"]
    assert "'P 1' → sub-P1" in warning and "P2" not in warning and "P3" not in warning


def test_code_list_column_with_a_text_code_is_not_a_numeric_column():
    # LimeSurvey exports "-oth-" next to the numeric codes 1..6 of a coded question
    rows = [(f"P{i}", "20", str(i % 6 + 1)) for i in range(12)] + [("P99", "20", "-oth-")]
    assert _problems(rows)["errors"] == []
