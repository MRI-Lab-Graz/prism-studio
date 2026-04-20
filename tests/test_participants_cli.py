from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRISM_TOOLS_APP = PROJECT_ROOT / "app" / "prism_tools.py"


def _run_prism_tools(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PRISM_TOOLS_APP), *args],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=30,
    )


def test_participants_preview_dataset_cli_json_output(tmp_path: Path) -> None:
    survey_dir = tmp_path / "rawdata" / "sub-01" / "ses-01" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-01_ses-01_task-test_survey.tsv").write_text(
        "participant_id\nsub-01\n",
        encoding="utf-8",
    )

    biometrics_dir = tmp_path / "rawdata" / "sub-02" / "ses-01" / "biometrics"
    biometrics_dir.mkdir(parents=True)
    (biometrics_dir / "sub-02_ses-01_task-test_biometrics.tsv").write_text(
        "value\n1\n",
        encoding="utf-8",
    )

    result = _run_prism_tools(
        "participants",
        "preview",
        "--mode",
        "dataset",
        "--project",
        str(tmp_path),
        "--json",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output

    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["total_participants"] == 2
    assert payload["participants"] == ["sub-01", "sub-02"]


def test_participants_convert_dataset_cli_json_output(tmp_path: Path) -> None:
    survey_dir = tmp_path / "rawdata" / "sub-03" / "ses-01" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-03_ses-01_task-test_survey.tsv").write_text(
        "participant_id\nsub-03\n",
        encoding="utf-8",
    )

    result = _run_prism_tools(
        "participants",
        "convert",
        "--mode",
        "dataset",
        "--project",
        str(tmp_path),
        "--json",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output

    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["participant_count"] == 1
    assert (tmp_path / "participants.tsv").exists()
    assert (tmp_path / "participants.json").exists()


def test_participants_save_mapping_cli_json_output(tmp_path: Path) -> None:
    result = _run_prism_tools(
        "participants",
        "save-mapping",
        "--mapping-json",
        '{"Age":"age"}',
        "--project",
        str(tmp_path),
        "--json",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output

    payload = json.loads(result.stdout)
    assert payload["status"] == "success"

    mapping_path = tmp_path / "code" / "library" / "participants_mapping.json"
    assert mapping_path.exists()

    saved_mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert saved_mapping["mappings"]["age"]["source_column"] == "Age"


def test_participants_merge_cli_json_preview_reports_conflicts(tmp_path: Path) -> None:
    (tmp_path / "participants.tsv").write_text(
        "participant_id\tage\tsex\n" "sub-001\t21\tF\n" "sub-002\t\tM\n",
        encoding="utf-8",
    )

    source_path = tmp_path / "participants_source.csv"
    source_path.write_text(
        "participant_id,age,group\n"
        "sub-001,22,control\n"
        "sub-002,30,control\n"
        "sub-003,25,patient\n",
        encoding="utf-8",
    )

    result = _run_prism_tools(
        "participants",
        "merge",
        "--input",
        str(source_path),
        "--project",
        str(tmp_path),
        "--json",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output

    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["action"] == "preview"
    assert payload["conflict_count"] == 1
    assert payload["fillable_value_count"] == 1
    assert payload["new_participant_count"] == 1
    assert payload["new_columns"] == ["group"]
    assert payload["can_apply"] is False
    assert payload["conflicts"][0]["participant_id"] == "sub-001"
    assert payload["conflicts"][0]["column"] == "age"


def test_participants_merge_cli_json_apply_updates_tsv_and_json(tmp_path: Path) -> None:
    (tmp_path / "participants.tsv").write_text(
        "participant_id\tsex\n" "sub-001\tF\n",
        encoding="utf-8",
    )
    (tmp_path / "participants.json").write_text(
        json.dumps(
            {
                "participant_id": {"Description": "Unique participant identifier"},
                "sex": {"Description": "Biological sex"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    source_path = tmp_path / "participants_source.csv"
    source_path.write_text(
        "participant_id,age,group\n" "sub-001,21,control\n" "sub-002,22,patient\n",
        encoding="utf-8",
    )

    result = _run_prism_tools(
        "participants",
        "merge",
        "--input",
        str(source_path),
        "--project",
        str(tmp_path),
        "--apply",
        "--json",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output

    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["action"] == "apply"
    assert payload["merged_participant_count"] == 2
    assert len(payload["backup_files"]) == 2
    for backup_path in payload["backup_files"]:
        assert Path(backup_path).exists()

    merged_lines = (
        (tmp_path / "participants.tsv").read_text(encoding="utf-8").splitlines()
    )
    assert merged_lines[0].split("\t") == ["participant_id", "sex", "age", "group"]
    assert merged_lines[1].split("\t") == ["sub-001", "F", "21", "control"]
    assert merged_lines[2].split("\t") == ["sub-002", "n/a", "22", "patient"]

    participants_json = json.loads(
        (tmp_path / "participants.json").read_text(encoding="utf-8")
    )
    assert set(participants_json) >= {"participant_id", "sex", "age", "group"}


def test_participants_merge_cli_conflicts_csv_exports_full_report(
    tmp_path: Path,
) -> None:
    (tmp_path / "participants.tsv").write_text(
        "participant_id\tage\tsex\n" "sub-001\t21\tF\n" "sub-002\t22\tM\n",
        encoding="utf-8",
    )

    source_path = tmp_path / "participants_source.csv"
    source_path.write_text(
        "participant_id,age,sex\n" "sub-001,25,F\n" "sub-002,22,X\n",
        encoding="utf-8",
    )

    result = _run_prism_tools(
        "participants",
        "merge",
        "--input",
        str(source_path),
        "--project",
        str(tmp_path),
        "--preview-limit",
        "1",
        "--conflicts-csv",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output

    reader = csv.DictReader(io.StringIO(result.stdout))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["participant_id"] == "sub-001"
    assert rows[0]["column"] == "age"
    assert rows[1]["participant_id"] == "sub-002"
    assert rows[1]["column"] == "sex"
