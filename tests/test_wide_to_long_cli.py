from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRISM_WRAPPER = PROJECT_ROOT / "prism.py"
PRISM_TOOLS_APP = PROJECT_ROOT / "app" / "prism_tools.py"


def _run_prism_tools(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PRISM_SKIP_VENV_CHECK"] = "1"
    return subprocess.run(
        [sys.executable, str(PRISM_TOOLS_APP), *args],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=30,
        env=env,
    )


def _run_prism(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PRISM_SKIP_VENV_CHECK"] = "1"
    return subprocess.run(
        [sys.executable, str(PRISM_WRAPPER), *args],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=30,
        env=env,
    )


def test_wide_to_long_cli_inspect_only_reports_rename_preview(tmp_path: Path) -> None:
    input_path = tmp_path / "wide.csv"
    pd.DataFrame(
        {
            "participant_id": ["sub-01"],
            "T1_score": ["1"],
            "T2_score": ["2"],
        }
    ).to_csv(input_path, index=False)

    result = _run_prism_tools(
        "wide-to-long",
        "--input",
        str(input_path),
        "--session-indicators",
        "T1_,T2_",
        "--inspect-only",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output
    assert "Rename preview:" in output
    assert "T1_score -> score (T1_)" in output
    assert "Inspect-only mode: no output file written." in output


def test_wide_to_long_cli_writes_output_file(tmp_path: Path) -> None:
    input_path = tmp_path / "wide.csv"
    output_path = tmp_path / "long.csv"
    pd.DataFrame(
        {
            "participant_id": ["sub-01"],
            "T1_score": ["1"],
            "T2_score": ["2"],
        }
    ).to_csv(input_path, index=False)

    result = _run_prism_tools(
        "wide-to-long",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--session-indicators",
        "T1_,T2_",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output
    assert output_path.exists()

    long_df = pd.read_csv(output_path, dtype=str)
    assert list(long_df.columns) == ["participant_id", "score", "session"]
    assert set(long_df["session"].tolist()) == {"T1_", "T2_"}


def test_prism_wrapper_delegates_wide_to_long_command(tmp_path: Path) -> None:
    input_path = tmp_path / "wide.csv"
    pd.DataFrame(
        {
            "participant_id": ["sub-01"],
            "T1_score": ["1"],
            "T2_score": ["2"],
        }
    ).to_csv(input_path, index=False)

    result = _run_prism(
        "wide-to-long",
        "--input",
        str(input_path),
        "--session-indicators",
        "T1_,T2_",
        "--inspect-only",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output
    assert "Wide-to-long inspection" in output


def test_wide_to_long_cli_json_inspect_output(tmp_path: Path) -> None:
    input_path = tmp_path / "wide.csv"
    pd.DataFrame(
        {
            "participant_id": ["sub-01"],
            "T1_score": ["1"],
            "T2_score": ["2"],
        }
    ).to_csv(input_path, index=False)

    result = _run_prism_tools(
        "wide-to-long",
        "--input",
        str(input_path),
        "--session-indicators",
        "T1_,T2_",
        "--inspect-only",
        "--json",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output

    payload = json.loads(result.stdout)
    assert payload["can_convert"] is True
    assert payload["detected_indicators"] == ["T1_", "T2_"]
    assert payload["rows_total"] == 2
    assert payload["column_rename_preview"][0]["output_column"] == "score"
