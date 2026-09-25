"""Backend environment conversion engine shared by Studio and
`prism_tools.py environment preview|convert` (src/environment_conversion.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.environment_conversion import (  # noqa: E402
    EnvironmentConversionCancelledError,
    perform_environment_conversion,
    preview_environment_file,
)


def _write_csv(path: Path, rows: int) -> Path:
    lines = ["timestamp,participant_id,latitude,longitude"]
    lines += [f"2025-01-{day:02d} 10:00:00,{day:02d},47.07,15.45" for day in range(1, rows + 1)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_preview_samples_five_rows_and_autodetects_columns(tmp_path):
    payload = preview_environment_file(_write_csv(tmp_path / "env.csv", rows=8), "auto")

    assert len(payload["sample"]) == 5
    assert payload["auto_detected"] == {
        "participant_id": "participant_id",
        "session": None,
        "timestamp": "timestamp",
        "location": None,
        "lat": "latitude",
        "lon": "longitude",
    }
    assert payload["compatibility"]["status"] == "compatible"


def test_conversion_stops_when_cancel_check_fires(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    logs: list[tuple[str, str]] = []

    with pytest.raises(EnvironmentConversionCancelledError):
        perform_environment_conversion(
            input_path=_write_csv(tmp_path / "env.csv", rows=2),
            filename="env.csv",
            suffix=".csv",
            separator_option="auto",
            timestamp_col="timestamp",
            participant_col="participant_id",
            participant_override=None,
            session_col=None,
            session_override="pre",
            location_col=None,
            lat_col="latitude",
            lon_col="longitude",
            location_label_override="",
            lat_manual=None,
            lon_manual=None,
            project_path=str(project),
            pilot_random_subject=False,
            log_callback=lambda message, level="info": logs.append((level, message)),
            cancel_check=lambda: True,
        )

    assert ("warning", "⏹️ Conversion cancelled by user") in logs
    assert not (project / "environment.tsv").exists()
