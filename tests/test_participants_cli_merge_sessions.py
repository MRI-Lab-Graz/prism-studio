"""CLI parity: answer the GUI's merge "Session Resolution" from the command line."""

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
    "3,baseline,22,1\n"
    "3,followup,23,1\n"
)
BASELINE = json.dumps(
    {"age": {"action": "pick_session", "session": "baseline", "session_column": "session"}}
)


def _merge(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    project = tmp_path / "proj"
    if not project.exists():
        project.mkdir()
        (project / "participants.tsv").write_text(
            "participant_id\tage\tsex\nsub-1\t30\t2\nsub-2\t40\t1\n", encoding="utf-8"
        )
    source = tmp_path / "in.csv"
    source.write_text(LONGITUDINAL_CSV, encoding="utf-8")
    return subprocess.run(
        [
            sys.executable, str(PRISM_TOOLS_APP), "participants", "merge",
            "--input", str(source), "--project", str(project),
            "--id-column", "participant_id", "--json", *extra,
        ],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(PROJECT_ROOT), timeout=60,
    )


def test_without_a_decision_the_merge_reports_that_a_session_choice_is_needed(tmp_path):
    payload = json.loads(_merge(tmp_path).stdout)

    assert payload["session_resolution_required"] is True
    assert payload["can_apply"] is False


def test_a_session_decision_makes_the_merge_applicable(tmp_path):
    result = _merge(tmp_path, "--session-resolution", BASELINE)

    payload = json.loads(result.stdout)
    assert payload["session_resolution_required"] is False
    assert payload["can_apply"] is True
    assert payload["new_participant_count"] == 1


def test_applying_with_a_session_decision_writes_the_chosen_session(tmp_path):
    result = _merge(tmp_path, "--session-resolution", BASELINE, "--apply")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = (tmp_path / "proj" / "participants.tsv").read_text().splitlines()
    rows = {line.split("\t")[0]: line.split("\t")[1] for line in lines[1:]}
    assert rows == {"sub-1": "30", "sub-2": "40", "sub-3": "22"}


def test_malformed_session_decision_json_is_rejected(tmp_path):
    result = _merge(tmp_path, "--session-resolution", "{not json")

    assert result.returncode == 2
    assert "Invalid JSON for --session-resolution" in (result.stdout + result.stderr)
    assert "unrecognized arguments" not in (result.stdout + result.stderr)
