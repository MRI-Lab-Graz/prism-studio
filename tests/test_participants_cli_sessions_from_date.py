"""CLI: participants merge/convert with --sessions-from-date on a repeated-ID file."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRISM_TOOLS_APP = PROJECT_ROOT / "app" / "prism_tools.py"

# One row per wave and no session column, as LimeSurvey exports it.
REPEATED_CSV = (
    "token,startdate,submitdate,age\n"
    "a,2026-09-01 10:00:00,x,31\n"
    "a,2026-03-01 10:00:00,x,30\n"
    "b,2026-03-02 10:00:00,x,40\n"
)
FIRST_WAVE = json.dumps(
    {"age": {"action": "pick_session", "session": "1", "session_column": "session"}}
)


def _run(tmp_path: Path, command: str, *extra: str) -> subprocess.CompletedProcess[str]:
    project = tmp_path / "proj"
    if not project.exists():
        project.mkdir()
        (project / "participants.tsv").write_text(
            "participant_id\tage\nsub-b\t40\n", encoding="utf-8"
        )
    source = tmp_path / "in.csv"
    source.write_text(REPEATED_CSV, encoding="utf-8")
    return subprocess.run(
        [
            sys.executable, str(PRISM_TOOLS_APP), "participants", command,
            "--input", str(source), "--project", str(project),
            "--id-column", "token", "--json", *extra,
        ],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(PROJECT_ROOT), timeout=60,
    )


def test_merge_without_the_flag_rejects_the_repeated_ids(tmp_path):
    result = _run(tmp_path, "merge")

    assert "non-unique" in result.stdout


def test_merge_with_the_flag_asks_for_a_session_choice_instead(tmp_path):
    payload = json.loads(_run(tmp_path, "merge", "--sessions-from-date").stdout)

    assert payload["session_resolution_column"] == "session"
    assert payload["session_resolution_required"] is True


def test_merge_apply_with_the_flag_writes_the_first_dated_wave(tmp_path):
    result = _run(
        tmp_path, "merge", "--sessions-from-date", "--session-resolution", FIRST_WAVE, "--apply"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    lines = (tmp_path / "proj" / "participants.tsv").read_text().splitlines()
    rows = {line.split("\t")[0]: line.split("\t")[1] for line in lines[1:]}
    assert rows == {"sub-a": "30", "sub-b": "40"}


def test_convert_with_the_flag_keeps_one_dated_session(tmp_path):
    result = _run(
        tmp_path, "convert", "--sessions-from-date", "--session-column", "session",
        "--session", "1", "--force",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    lines = (tmp_path / "proj" / "participants.tsv").read_text().splitlines()
    rows = {line.split("\t")[0]: line.split("\t")[1] for line in lines[1:]}
    assert rows == {"sub-a": "30", "sub-b": "40"}


def test_preview_with_the_flag_lists_the_dated_sessions(tmp_path):
    payload = json.loads(_run(tmp_path, "preview", "--sessions-from-date").stdout)

    assert payload["participant_count"] == 3
    assert any(c.get("column") == "session" for c in payload["session_candidates"])


def test_flag_without_an_id_column_is_a_clear_error(tmp_path):
    (tmp_path / "in.csv").write_text(REPEATED_CSV, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable, str(PRISM_TOOLS_APP), "participants", "preview",
            "--input", str(tmp_path / "in.csv"), "--sessions-from-date",
        ],
        capture_output=True, text=True, encoding="utf-8", cwd=str(PROJECT_ROOT), timeout=60,
    )

    assert result.returncode == 2
    assert "ID column" in result.stdout
