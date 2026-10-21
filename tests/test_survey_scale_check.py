"""Answers outside a template's scale are listed in the preview with the participants who gave them."""

import pandas as pd

from src.survey_scale_check import find_scale_violations

LIKERT = {"Levels": {"0": "never", "1": "sometimes", "2": "often"}}


def _find(values, item_def=LIKERT, ids=None):
    ids = ids or [f"P{i}" for i in range(1, len(values) + 1)]
    df = pd.DataFrame({"pid": ids, "Q1": values})
    return find_scale_violations(df, "Q1", item_def, "pid", lambda v: str(v).strip().lower() in {"", "n/a", "nan"})


def test_values_on_the_scale_and_missing_values_are_fine():
    assert _find(["0", "1", "2", "", "n/a", " 2 ", "1.0"]) == []


def test_numbers_outside_the_scale_are_out_of_range_with_participants():
    (issue,) = _find(["1", "9", "-1", "2"])
    assert issue["type"] == "out_of_range" and issue["severity"] == "error"
    assert issue["out_of_range_count"] == 2
    assert issue["range"] == "0-2"
    assert issue["examples"] == ["P2: 9", "P3: -1"]
    assert "P2" in issue["message"]


def test_text_in_a_numeric_scale_is_an_unexpected_value():
    (issue,) = _find(["1", "often", "2"])
    assert issue["type"] == "unexpected_values"
    assert issue["unexpected"] == ["often"] and issue["examples"] == ["P2: often"]


def test_a_number_between_levels_is_unexpected_not_out_of_range():
    (issue,) = _find(["1", "1.5"])
    assert issue["type"] == "unexpected_values" and issue["unexpected"] == ["1.5"]


def test_text_levels_accept_exactly_those_values():
    yes_no = {"Levels": {"yes": "Yes", "no": "No"}}
    assert _find(["yes", "no"], yes_no) == []
    (issue,) = _find(["yes", "maybe"], yes_no)
    assert issue["type"] == "unexpected_values"


def test_items_without_levels_are_not_checked():
    assert _find(["anything", "9"], {"Description": "free text"}) == []
    assert _find(["x"], None) == []


def test_many_violations_are_counted_and_examples_capped():
    (issue,) = _find([str(v) for v in range(10, 30)])
    assert issue["out_of_range_count"] == 20 and len(issue["examples"]) == 5


def test_dry_run_preview_lists_the_violations_unless_a_task_offset_is_set(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    src = tmp_path / "s.csv"
    src.write_text("participant_id,BRS01,BRS02,BRS03\nP001,9,4,2\nP002,often,1,1\n")
    root = Path(__file__).resolve().parents[1]
    base = [sys.executable, str(root / "prism_tools.py"), "survey", "convert", "--input", str(src),
            "--output", str(tmp_path / "out"), "--session", "1", "--dry-run",
            "--library", str(root / "official" / "library" / "survey")]
    env = {**__import__("os").environ, "PRISM_SKIP_VENV_CHECK": "1"}
    plain = subprocess.run(base, capture_output=True, text=True, encoding="utf-8", env=env).stdout
    assert "P001: 9" in plain and "P002: often" in plain
    shifted = subprocess.run(base + ["--value-offset", "brs=1"], capture_output=True, text=True, encoding="utf-8", env=env).stdout
    assert "P001: 9" not in shifted
