"""Converters tell the user when a label was changed to make it BIDS-safe (letters and digits only)."""

from src.cleaning_notes import cleaning_note, missing_id_note


def test_unchanged_labels_and_prefixes_give_no_note():
    assert cleaning_note(["P1", "sub-P2", "SUB-P3", "007"], ["sub-P1", "sub-P2", "sub-P3", "sub-007"], "participant ID", "sub-") == ""


def test_changed_labels_are_listed_once_with_the_result():
    note = cleaning_note(["P 1", "P 1", "P/2", "ok"], ["sub-P1", "sub-P1", "sub-P2", "sub-ok"], "participant ID", "sub-")
    assert note.startswith("2 participant ID(s) were cleaned")
    assert "'P 1' → sub-P1" in note and "'P/2' → sub-P2" in note and "ok" not in note
    assert note.count("P 1") == 1


def test_session_labels_use_their_prefix_and_many_changes_are_summarised():
    assert "'pre test' → ses-pretest" in cleaning_note(["pre test"], ["ses-pretest"], "session label", "ses-")
    note = cleaning_note([f"a b{i}" for i in range(8)], [f"ses-ab{i}" for i in range(8)], "session label", "ses-")
    assert "8 session label(s)" in note and "more" in note


def test_empty_results_are_ignored_here_they_are_the_missing_id_note():
    assert cleaning_note(["???"], [""], "participant ID", "sub-") == ""


def test_missing_ids_name_the_rows():
    assert missing_id_note([2, 3, 4]) == "3 row(s) have no participant ID and will be skipped (data rows 2, 3, 4)."
    assert missing_id_note([]) == ""


def test_survey_dry_run_reports_skipped_rows_and_cleaned_labels(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    src = tmp_path / "s.csv"
    src.write_text("participant_id,BRS01,BRS02,BRS03\nP9,2,2,2\n,3,4,2\nP 1,1,0,2\n")
    root = Path(__file__).resolve().parents[1]
    out = subprocess.run(
        [sys.executable, str(root / "prism_tools.py"), "survey", "convert", "--input", str(src),
         "--output", str(tmp_path / "out"), "--session", "pre test", "--dry-run",
         "--library", str(root / "official" / "library" / "survey")],
        capture_output=True, text=True, env={**os.environ, "PRISM_SKIP_VENV_CHECK": "1"},
    ).stdout
    assert "no participant ID and will be skipped (data rows 2)" in out
    assert "'P 1' → sub-P1" in out
    assert "'pre test' → ses-pretest" in out
    assert "Total files to create: 2" in out  # the row without an ID is not planned
