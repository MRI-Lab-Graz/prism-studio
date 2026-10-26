"""Validator x environment 2.0.0: columns go through the term registry like biosample.

Plan: docs/superpowers/plans/2026-10-26-environment-terms-phase-b-studio.md (Task 3).
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from schema_manager import load_all_schemas
from src.specification import load_specification, use_specification
from validator import DatasetValidator

REPO = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO / "app" / "schemas"
BASE = "sub-01/ses-1/environment/sub-01_ses-1_recording-weather_environment"
RETIRED = "environment format 1.1.0 is retired; re-create it with: python prism_tools.py environment convert ..."

ID_COLUMNS = {
    "subject_id": {"Description": "Participant", "Units": "n/a"},
    "session_id": {"Description": "Session", "Units": "n/a"},
}
V2_COLUMNS = {
    "temp_c": {"Term": "prism:air-temperature"},
    "temp_max_3d": {
        "Term": "prism:air-temperature",
        "Window": {"Start": "P3D", "End": "PT0S"},
        "Statistic": "max",
    },
    "season_code": {"Term": "prism:season"},
}


def _sidecar(columns):
    return {
        "Technical": {"Source": "open-meteo"},
        "Study": {"EnvironmentName": "weather"},
        "Metadata": {"SchemaVersion": "2.0.0", "CreationDate": "2026-10-26"},
        **ID_COLUMNS,
        **columns,
    }


def _project(root: Path, sidecar: dict, header: list, row: list) -> Path:
    (root / "recording-weather_environment.json").write_text(json.dumps(sidecar), encoding="utf-8")
    tsv = root / f"{BASE}.tsv"
    tsv.parent.mkdir(parents=True, exist_ok=True)
    tsv.write_text("\t".join(header) + "\n" + "\t".join(row) + "\n", encoding="utf-8")
    return tsv


def _issues(root: Path, tsv: Path):
    with use_specification(load_specification(project_root=root)):
        v = DatasetValidator(load_all_schemas(str(SCHEMA_DIR)))
        return v.validate_sidecar(str(tsv), "environment", str(root)) + v.validate_data_content(
            str(tsv), "environment", str(root)
        )


def _msgs(issues, level):
    return [m for lvl, m, *_ in issues if lvl == level]


def _v2(tmp_path, extra_columns=None, extra_values=None, season="winter"):
    columns = {**V2_COLUMNS, **(extra_columns or {})}
    header = ["subject_id", "session_id", "temp_c", "temp_max_3d", "season_code", *(extra_values or {})]
    row = ["sub-01", "ses-1", "3.5", "7.0", season, *(extra_values or {}).values()]
    return _issues(tmp_path, _project(tmp_path, _sidecar(columns), header, row))


def test_v2_environment_file_valid(tmp_path):
    issues = _v2(tmp_path)
    assert not _msgs(issues, "ERROR") and not _msgs(issues, "WARNING"), issues


def test_unit_differs_is_info(tmp_path):
    issues = _v2(tmp_path, {"temp_c": {"Term": "prism:air-temperature", "Units": "degF"}})
    assert not _msgs(issues, "ERROR"), issues
    assert len([m for m in _msgs(issues, "INFO") if "degF" in m]) == 1


def test_unknown_column_is_info(tmp_path):
    issues = _v2(
        tmp_path,
        {"noise_db": {"Description": "Street noise", "Units": "dB"}},
        {"noise_db": "55"},
    )
    assert not _msgs(issues, "ERROR") and not _msgs(issues, "WARNING"), issues
    assert any("noise_db" in m and "not an official" in m for m in _msgs(issues, "INFO"))


def test_level_outside_term_levels_warns(tmp_path):
    issues = _v2(tmp_path, season="monsoon")
    assert not _msgs(issues, "ERROR"), issues
    assert any("monsoon" in m for m in _msgs(issues, "WARNING"))


def test_sidecar_own_levels_keep_error(tmp_path):
    issues = _v2(
        tmp_path,
        {"site": {"Description": "Site", "Units": "n/a", "Levels": {"a": "A", "b": "B"}}},
        {"site": "c"},
    )
    assert any("'c'" in m for m in _msgs(issues, "ERROR"))


def test_timestamp_column_warns(tmp_path):
    issues = _v2(tmp_path, extra_values={"timestamp": "2026-10-26T10:00"})
    assert not _msgs(issues, "ERROR"), issues
    assert any("timestamp" in m for m in _msgs(issues, "WARNING"))


def test_old_format_is_retired(tmp_path):
    old = {
        "Technical": {"Source": "open-meteo"},
        "Study": {"EnvironmentName": "weather"},
        "Privacy": {"AnchorField": "relative_time"},
        "Columns": {"temp_c": {"Description": "Temperature", "Units": "degC"}},
        "Metadata": {"SchemaVersion": "1.1.0", "CreationDate": "2025-01-01"},
    }
    tsv = _project(tmp_path, old, ["subject_id", "session_id", "relative_time", "hour_bin"],
                   ["sub-01", "ses-1", "0", "evening"])
    issues = _issues(tmp_path, tsv)
    sidecar = (tmp_path / "recording-weather_environment.json").as_posix()
    assert issues == [("ERROR", f"{sidecar}: {RETIRED}")]


def test_local_environment_term_used(tmp_path):
    folder = tmp_path / "code" / "specification" / "terms" / "environment"
    folder.mkdir(parents=True)
    (folder / "noise-level.json").write_text(json.dumps({
        "TermID": "prism:noise-level",
        "Level": "variable",
        "Label": "noise level",
        "Aliases": ["noise_db"],
        "Description": "Sound pressure level at the site.",
        "Units": "dB",
    }), encoding="utf-8")
    issues = _v2(tmp_path, {"noise_db": {"Term": "prism:noise-level"}}, {"noise_db": "55"})
    assert not _msgs(issues, "ERROR") and not _msgs(issues, "WARNING"), issues
    notes = [m for m in _msgs(issues, "INFO") if "uses the local term" in m]
    assert len(notes) == 1 and "prism:noise-level" in notes[0]


def test_retired_sidecar_detection():
    from validator import is_retired_environment_sidecar

    assert is_retired_environment_sidecar({"Columns": {}})
    assert is_retired_environment_sidecar({"Metadata": {"SchemaVersion": "1.1.0"}})
    assert not is_retired_environment_sidecar(_sidecar(V2_COLUMNS))
