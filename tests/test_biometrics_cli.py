from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

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


def _write_biometrics_template(library_dir: Path, task_name: str) -> Path:
    template_path = library_dir / f"biometrics-{task_name}.json"
    template_path.write_text(
        json.dumps(
            {
                "Technical": {"Device": "Grip meter"},
                "Study": {"TaskName": task_name},
                "Metadata": {"SchemaVersion": "1.2.0"},
                "grip_strength": {"Description": "Dominant-hand grip strength"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return template_path


def test_biometrics_detect_cli_json_output(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir()
    _write_biometrics_template(library_dir, "grip")

    input_path = tmp_path / "biometrics.csv"
    pd.DataFrame(
        {
            "participant_id": ["sub-01"],
            "session": ["ses-01"],
            "grip_strength": [42],
        }
    ).to_csv(input_path, index=False)

    result = _run_prism_tools(
        "biometrics",
        "detect",
        "--input",
        str(input_path),
        "--library",
        str(library_dir),
        "--json",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output

    payload = json.loads(result.stdout)
    assert payload["tasks"] == ["grip"]


def test_biometrics_convert_cli_writes_prism_dataset(tmp_path: Path) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir()
    _write_biometrics_template(library_dir, "grip")

    input_path = tmp_path / "biometrics.csv"
    pd.DataFrame(
        {
            "participant_id": ["01", "02"],
            "session": ["1", "2"],
            "grip_strength": [42, 36],
        }
    ).to_csv(input_path, index=False)

    output_dir = tmp_path / "dataset"
    result = _run_prism_tools(
        "biometrics",
        "convert",
        "--input",
        str(input_path),
        "--library",
        str(library_dir),
        "--output",
        str(output_dir),
        "--tasks",
        "grip",
        "--name",
        "Biometrics Smoke Test",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output
    assert "Converted biometrics.csv" in output
    assert "Tasks: grip" in output

    dataset_description = json.loads(
        output_dir.joinpath("dataset_description.json").read_text(encoding="utf-8")
    )
    assert dataset_description["Name"] == "Biometrics Smoke Test"

    participants_tsv = output_dir / "participants.tsv"
    assert participants_tsv.exists()
    participants_df = pd.read_csv(participants_tsv, sep="\t", dtype=str)
    assert participants_df["participant_id"].tolist() == ["sub-01", "sub-02"]

    sidecar_path = output_dir / "task-grip_biometrics.json"
    assert sidecar_path.exists()

    first_tsv = output_dir / "sub-01" / "ses-01" / "biometrics" / "sub-01_ses-01_task-grip_biometrics.tsv"
    second_tsv = output_dir / "sub-02" / "ses-02" / "biometrics" / "sub-02_ses-02_task-grip_biometrics.tsv"
    assert first_tsv.exists()
    assert second_tsv.exists()

    first_df = pd.read_csv(first_tsv, sep="\t", dtype=str)
    second_df = pd.read_csv(second_tsv, sep="\t", dtype=str)
    assert first_df.to_dict(orient="records") == [{"grip_strength": "42"}]
    assert second_df.to_dict(orient="records") == [{"grip_strength": "36"}]