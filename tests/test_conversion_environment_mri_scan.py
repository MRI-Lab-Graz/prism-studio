import json
import os
import pandas as pd
from pathlib import Path

from flask import Flask

from src.web.blueprints.conversion_environment_handlers import (
    api_environment_scan_mri_acquisition,
)
from src.web.blueprints.conversion_environment_mri_scan_helpers import (
    build_mri_acquisition_table,
    discover_mri_acquisition_rows,
    extract_sidecar_location,
    parse_sidecar_timestamp,
)


def _write_sidecar(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_parse_sidecar_timestamp_prefers_acquisition_datetime():
    dt = parse_sidecar_timestamp({"AcquisitionDateTime": "2026-02-26T14:30:00"})
    assert dt is not None
    assert dt.isoformat() == "2026-02-26T14:30:00"


def test_parse_sidecar_timestamp_pads_single_digit_seconds():
    dt = parse_sidecar_timestamp({"AcquisitionDateTime": "2026-02-26T14:30:2.5"})
    assert dt is not None
    assert dt.second == 2


def test_parse_sidecar_timestamp_falls_back_to_date_time_pairs():
    dt = parse_sidecar_timestamp(
        {"AcquisitionDate": "2026-02-26", "AcquisitionTime": "09:15:00"}
    )
    assert dt is not None
    assert dt.hour == 9 and dt.minute == 15


def test_parse_sidecar_timestamp_falls_back_to_study_date_time():
    dt = parse_sidecar_timestamp(
        {"StudyDate": "2026-02-26", "StudyTime": "08:00:00"}
    )
    assert dt is not None
    assert dt.hour == 8


def test_parse_sidecar_timestamp_returns_none_when_no_tags_present():
    assert parse_sidecar_timestamp({"Manufacturer": "Siemens"}) is None


def test_extract_sidecar_location_prefers_institution_address():
    label = extract_sidecar_location(
        {"InstitutionAddress": "8010 Graz, Austria", "InstitutionName": "MUG"}
    )
    assert label == "8010 Graz, Austria"


def test_extract_sidecar_location_falls_back_to_institution_name():
    label = extract_sidecar_location({"InstitutionName": "MUG"})
    assert label == "MUG"


def test_extract_sidecar_location_empty_when_no_tags():
    assert extract_sidecar_location({}) == ""


def test_discover_rows_picks_earliest_timestamp_across_modalities(tmp_path):
    rawdata = tmp_path / "rawdata"
    _write_sidecar(
        rawdata / "sub-01" / "ses-01" / "func" / "sub-01_ses-01_task-rest_bold.json",
        {"AcquisitionDateTime": "2026-02-26T15:00:00"},
    )
    _write_sidecar(
        rawdata / "sub-01" / "ses-01" / "anat" / "sub-01_ses-01_T1w.json",
        {"AcquisitionDateTime": "2026-02-26T14:30:00"},
    )

    rows = discover_mri_acquisition_rows(rawdata)

    assert len(rows) == 1
    assert rows[0]["participant_id"] == "sub-01"
    assert rows[0]["session_id"] == "ses-01"
    assert rows[0]["timestamp"] == "2026-02-26T14:30:00"


def test_discover_rows_picks_up_institution_location_from_any_sidecar(tmp_path):
    rawdata = tmp_path / "rawdata"
    _write_sidecar(
        rawdata / "sub-02" / "ses-01" / "anat" / "sub-02_ses-01_T1w.json",
        {"AcquisitionDateTime": "2026-02-26T10:00:00"},
    )
    _write_sidecar(
        rawdata / "sub-02" / "ses-01" / "func" / "sub-02_ses-01_task-rest_bold.json",
        {
            "AcquisitionDateTime": "2026-02-26T10:15:00",
            "InstitutionAddress": "8010 Graz, Austria",
        },
    )

    rows = discover_mri_acquisition_rows(rawdata)

    assert len(rows) == 1
    assert rows[0]["location"] == "8010 Graz, Austria"
    assert rows[0]["timestamp"] == "2026-02-26T10:00:00"


def test_discover_rows_skips_sidecars_with_no_usable_tags(tmp_path):
    rawdata = tmp_path / "rawdata"
    _write_sidecar(
        rawdata / "sub-03" / "ses-01" / "anat" / "sub-03_ses-01_T1w.json",
        {"Manufacturer": "Siemens"},
    )

    rows = discover_mri_acquisition_rows(rawdata)

    assert rows == []


def test_discover_rows_returns_empty_for_missing_rawdata(tmp_path):
    assert discover_mri_acquisition_rows(tmp_path / "does-not-exist") == []


def test_build_mri_acquisition_table_reports_stats_and_missing_subjects(tmp_path):
    rawdata = tmp_path / "rawdata"
    _write_sidecar(
        rawdata / "sub-01" / "ses-01" / "anat" / "sub-01_ses-01_T1w.json",
        {"AcquisitionDateTime": "2026-02-26T14:30:00"},
    )
    _write_sidecar(
        rawdata / "sub-02" / "ses-01" / "anat" / "sub-02_ses-01_T1w.json",
        {"Manufacturer": "Siemens"},
    )

    df, stats = build_mri_acquisition_table(rawdata)

    assert list(df.columns) == [
        "participant_id",
        "session_id",
        "timestamp",
        "location",
        "filename",
    ]
    assert len(df) == 1
    assert stats["subjects_found"] == 2
    assert stats["rows_with_timestamp"] == 1
    assert stats["subjects_missing_timestamp"] == ["sub-02"]


def test_build_mri_acquisition_table_empty_when_no_rawdata(tmp_path):
    df, stats = build_mri_acquisition_table(tmp_path / "rawdata")
    assert df.empty
    assert stats["subjects_found"] == 0


def _make_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(32)
    return app


def test_api_scan_mri_acquisition_writes_temp_tsv_for_found_rows(tmp_path):
    project_root = tmp_path / "demo_project"
    _write_sidecar(
        project_root / "rawdata" / "sub-01" / "ses-01" / "anat" / "sub-01_ses-01_T1w.json",
        {"AcquisitionDateTime": "2026-02-26T14:30:00"},
    )

    app = _make_app()
    with app.test_request_context(
        "/api/environment-scan-mri",
        method="POST",
        data={"project_path": str(project_root)},
    ):
        response = api_environment_scan_mri_acquisition()

    body = response.get_json()
    assert body["success"] is True
    assert body["row_count"] == 1

    written_path = Path(body["source_file_path"])
    assert written_path.exists()
    df = pd.read_csv(written_path, sep="\t")
    assert list(df["participant_id"]) == ["sub-01"]
    written_path.unlink()


def test_api_scan_mri_acquisition_errors_when_no_timestamps_found(tmp_path):
    project_root = tmp_path / "demo_project"
    project_root.mkdir(parents=True, exist_ok=True)

    app = _make_app()
    with app.test_request_context(
        "/api/environment-scan-mri",
        method="POST",
        data={"project_path": str(project_root)},
    ):
        response = api_environment_scan_mri_acquisition()

    status_code = response[1] if isinstance(response, tuple) else 200
    body = response[0].get_json() if isinstance(response, tuple) else response.get_json()
    assert status_code == 400
    assert body["success"] is False
    assert "No MRI acquisition timestamps" in body["error"]


def test_api_scan_mri_acquisition_errors_when_no_project_selected():
    app = _make_app()
    with app.test_request_context("/api/environment-scan-mri", method="POST"):
        response = api_environment_scan_mri_acquisition()

    status_code = response[1] if isinstance(response, tuple) else 200
    body = response[0].get_json() if isinstance(response, tuple) else response.get_json()
    assert status_code == 400
    assert body["success"] is False
