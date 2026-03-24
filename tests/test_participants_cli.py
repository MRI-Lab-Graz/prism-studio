from __future__ import annotations

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