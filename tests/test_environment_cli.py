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


def test_environment_preview_cli_json_output(tmp_path: Path) -> None:
    input_path = tmp_path / "environment.csv"
    input_path.write_text(
        "participant_id,session,timestamp,location\n"
        "sub-01,ses-01,2026-03-24 10:00:00,Berlin\n",
        encoding="utf-8",
    )

    result = _run_prism_tools(
        "environment",
        "preview",
        "--input",
        str(input_path),
        "--separator",
        "auto",
        "--json",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output

    payload = json.loads(result.stdout)
    assert payload["columns"] == ["participant_id", "session", "timestamp", "location"]
    assert payload["auto_detected"]["participant_id"] == "participant_id"
    assert payload["auto_detected"]["session"] == "session"
    assert payload["auto_detected"]["timestamp"] == "timestamp"
    assert payload["auto_detected"]["location"] == "location"
    assert payload["compatibility"]["status"] == "compatible"
    assert payload["sample"][0][0] == "sub-01"


def _seeded_cache(project: Path, days: list[str]) -> None:
    """Provider data for each day in the project's cache, so the CLI run needs no network."""
    entries = {}
    for day in days:
        times = [f"{day}T{h:02d}:00" for h in range(24)]
        entries[f"{day}|47.0700|15.4500"] = {
            key: {"hourly": {"time": times, var: [float(day[-2:])] * 24}}
            for key, var in (("weather", "temperature_2m"), ("air", "pm2_5"), ("pollen", "birch_pollen"))
        }
    (project / ".prism").mkdir(parents=True)
    (project / ".prism" / "environment_provider_cache.json").write_text(
        json.dumps({"version": 1, "entries": entries}), encoding="utf-8"
    )


def test_cli_window_option(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "single"}}), encoding="utf-8")
    _seeded_cache(project, ["2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04"])
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    input_path = input_dir / "env.csv"
    input_path.write_text("pid,ts\nP1,2025-06-04 10:00\n", encoding="utf-8")

    result = _run_prism_tools(
        "environment", "convert", "--input", str(input_path), "--project", str(project),
        "--timestamp-col", "ts", "--participant-col", "pid", "--session-override", "1",
        "--lat", "47.07", "--lon", "15.45", "--window", "temp_c:P3D:max", "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    tsv = next(project.glob("sub-*/ses-*/environment/*_environment.tsv"))
    header, row = tsv.read_text(encoding="utf-8").splitlines()[:2]
    assert dict(zip(header.split("\t"), row.split("\t")))["temp_c_max_p3d"] == "4.0"
    sidecar = json.loads((project / "recording-weather_environment.json").read_text(encoding="utf-8"))
    assert sidecar["temp_c_max_p3d"]["Window"] == {"Start": "P3D", "End": "PT0S"}
    assert sidecar["temp_c_max_p3d"]["Statistic"] == "max"


def test_cli_window_option_refuses_a_bad_value(tmp_path: Path) -> None:
    input_path = tmp_path / "env.csv"
    input_path.write_text("pid,ts\nP1,2025-06-04 10:00\n", encoding="utf-8")
    result = _run_prism_tools(
        "environment", "convert", "--input", str(input_path), "--project", str(tmp_path),
        "--timestamp-col", "ts", "--window", "temp_c:P1M:max",
    )
    assert result.returncode != 0
    assert "fixed length" in result.stdout + result.stderr
