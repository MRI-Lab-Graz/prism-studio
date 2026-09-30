"""CLI parity: answer the GUI's merge "Harmonization Decisions" from the command line."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRISM_TOOLS_APP = PROJECT_ROOT / "app" / "prism_tools.py"

EXISTING_TSV = "participant_id\tage\tsex\nsub-1\t30\t1\nsub-2\t40\t2\nsub-3\t50\t1\nsub-4\t35\t2\n"
# Same people, other coding of sex (M/F instead of 1/2), plus one new participant.
INCOMING_CSV = "participant_id,age,sex\n1,30,M\n2,40,F\n3,50,M\n4,35,F\n5,22,M\n"


def _merge(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    project = tmp_path / "proj"
    if not project.exists():
        project.mkdir()
        (project / "participants.tsv").write_text(EXISTING_TSV, encoding="utf-8")
    source = tmp_path / "in.csv"
    source.write_text(INCOMING_CSV, encoding="utf-8")
    return subprocess.run(
        [
            sys.executable, str(PRISM_TOOLS_APP), "participants", "merge",
            "--input", str(source), "--project", str(project),
            "--id-column", "participant_id", "--json", *extra,
        ],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(PROJECT_ROOT), timeout=60,
    )


def _table(tmp_path: Path) -> list[dict[str, str]]:
    lines = (tmp_path / "proj" / "participants.tsv").read_text().splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"))) for line in lines[1:]]


def test_preview_lists_the_harmonization_candidate_and_keeps_existing_by_default(tmp_path):
    payload = json.loads(_merge(tmp_path).stdout)

    candidate = payload["harmonization_candidates"][0]
    assert candidate["column"] == "sex"
    assert payload["harmonization_decisions"]["sex"]["action"] == "keep_existing"


def test_use_incoming_relabels_the_whole_column(tmp_path):
    result = _merge(tmp_path, "--harmonization", '{"sex": {"action": "use_incoming"}}', "--apply")

    assert result.returncode == 0, result.stdout + result.stderr
    assert [row["sex"] for row in _table(tmp_path)] == ["M", "F", "M", "F", "M"]


def test_keep_both_adds_the_incoming_coding_in_a_new_column(tmp_path):
    decision = '{"sex": {"action": "keep_both", "new_column": "sex_v2"}}'
    result = _merge(tmp_path, "--harmonization", decision, "--apply")

    assert result.returncode == 0, result.stdout + result.stderr
    rows = _table(tmp_path)
    assert [row["sex"] for row in rows] == ["1", "2", "1", "2", "1"]
    assert [row["sex_v2"] for row in rows] == ["M", "F", "M", "F", "M"]


def test_the_preview_reports_the_applied_decision(tmp_path):
    result = _merge(tmp_path, "--harmonization", '{"sex": {"action": "use_incoming"}}')

    assert json.loads(result.stdout)["harmonization_decisions"]["sex"]["action"] == "use_incoming"


def test_an_unknown_action_falls_back_to_keep_existing_like_the_gui(tmp_path):
    result = _merge(tmp_path, "--harmonization", '{"sex": {"action": "use-incoming"}}', "--apply")

    assert result.returncode == 0, result.stdout + result.stderr
    assert [row["sex"] for row in _table(tmp_path)] == ["1", "2", "1", "2", "1"]


def test_malformed_harmonization_json_is_rejected(tmp_path):
    result = _merge(tmp_path, "--harmonization", "{not json")

    assert result.returncode == 2
    assert "Invalid JSON for --harmonization" in (result.stdout + result.stderr)
    assert "unrecognized arguments" not in (result.stdout + result.stderr)
