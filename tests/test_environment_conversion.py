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


# ── environment 2.0.0 output (plan B, Task 4) ──────────────────────────────

import json  # noqa: E402

import jsonschema  # noqa: E402

import src.environment_conversion as ec  # noqa: E402
from src.term_registry import find_term, load_registry  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
VALUE_COLUMNS = [c for c in ec.OUTPUT_COLUMNS if c not in ("subject_id", "session_id")]


def test_sidecar_is_v2_and_valid():
    sidecar = ec._build_environment_sidecar()
    schema = json.loads(
        (REPO / "app" / "schemas" / "stable" / "environment.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(sidecar, schema)
    assert sidecar["Metadata"]["SchemaVersion"] == "2.0.0"
    registry = load_registry("environment")
    for column in VALUE_COLUMNS:
        key, term = find_term(registry, column)  # a column without a term fails here
        assert sidecar[column] == {"Term": term["TermID"]}
    assert sidecar["subject_id"] == {"Description": "BIDS subject identifier", "Units": "n/a"}
    assert sidecar["session_id"] == {"Description": "BIDS session identifier", "Units": "n/a"}


def test_no_privacy_or_relative_time():
    sidecar = ec._build_environment_sidecar()
    for gone in ("Privacy", "Provenance", "Columns", "filename", "relative_time"):
        assert gone not in sidecar
    assert "filename" not in ec.OUTPUT_COLUMNS and "relative_time" not in ec.OUTPUT_COLUMNS
    row = ec._compute_row(ec.datetime(2025, 1, 1, 10), "sub-01", "ses-1", 47.0)
    assert set(row) == set(ec.OUTPUT_COLUMNS)


def test_weather_regime_codes_english():
    from src.environment_provider_helpers import handle_extract_environment_hour

    codes = set()
    for pressure in (1030.0, 990.0, 1010.0):
        out = handle_extract_environment_hour(
            ec.datetime(2025, 1, 1, 10),
            {"weather": {"hourly": {"time": ["2025-01-01T10:00"], "surface_pressure": [pressure]}}, "air": {}, "pollen": {}},
            hourly_value=ec._hourly_value,
            pollen_risk_bin=ec._pollen_risk_bin,
        )
        codes.add(out["weather_regime"])
    assert codes == {"high-pressure", "low-pressure", "frontal"}


def test_convert_then_validate_has_no_error(tmp_path, monkeypatch):
    from schema_manager import load_all_schemas
    from src.specification import load_specification, use_specification
    from validator import DatasetValidator

    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "single"}}), encoding="utf-8")
    monkeypatch.setattr(ec, "_fetch_environment_day", lambda *a, **k: ({"weather": {}, "air": {}, "pollen": {}}, []))
    ec.perform_environment_conversion(
        input_path=_write_csv(tmp_path / "env.csv", rows=2),
        filename="env.csv", suffix=".csv", separator_option="auto",
        timestamp_col="timestamp", participant_col="participant_id", participant_override=None,
        session_col=None, session_override="1", location_col=None,
        lat_col="latitude", lon_col="longitude", location_label_override="",
        lat_manual=None, lon_manual=None, project_path=str(project),
        pilot_random_subject=False, log_callback=lambda *a, **k: None,
    )
    tsvs = list(project.glob("sub-*/ses-*/environment/*_environment.tsv"))
    assert tsvs
    header = tsvs[0].read_text(encoding="utf-8").splitlines()[0].split("\t")
    assert "filename" not in header and "relative_time" not in header
    with use_specification(load_specification(project_root=project)):
        v = DatasetValidator(load_all_schemas(str(REPO / "app" / "schemas")))
        issues = v.validate_sidecar(str(tsvs[0]), "environment", str(project)) + v.validate_data_content(
            str(tsvs[0]), "environment", str(project)
        )
    assert not [i for i in issues if i[0] == "ERROR"], issues
