"""CLI parity for the longitudinal session choice (GUI: session picker)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRISM_TOOLS_APP = PROJECT_ROOT / "app" / "prism_tools.py"

LONGITUDINAL_CSV = (
    "participant_id,session,age,sex\n"
    "1,baseline,30,2\n"
    "1,followup,31,2\n"
    "2,baseline,40,1\n"
    "2,followup,41,1\n"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PRISM_TOOLS_APP), "participants", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(PROJECT_ROOT),
        timeout=60,
    )


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "data.csv"
    source.write_text(LONGITUDINAL_CSV, encoding="utf-8")
    return source


def test_preview_json_lists_session_candidates(tmp_path):
    result = _run(
        "preview", "--input", str(_source(tmp_path)), "--project", str(tmp_path),
        "--id-column", "participant_id", "--json",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["session_candidates"] == [
        {"column": "session", "values": ["baseline", "followup"]}
    ]


def test_convert_with_a_chosen_session_writes_one_row_per_participant(tmp_path):
    result = _run(
        "convert", "--input", str(_source(tmp_path)), "--project", str(tmp_path),
        "--id-column", "participant_id",
        "--session-column", "session", "--session", "followup", "--json",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["rows"] == 2
    lines = (tmp_path / "participants.tsv").read_text().splitlines()
    assert [line.split("\t")[1] for line in lines[1:]] == ["31", "41"]


def test_convert_without_a_session_choice_stops(tmp_path):
    result = _run(
        "convert", "--input", str(_source(tmp_path)), "--project", str(tmp_path),
        "--id-column", "participant_id", "--json",
    )

    assert result.returncode != 0
    assert "one row per participant" in result.stdout
    assert not (tmp_path / "participants.tsv").exists()
