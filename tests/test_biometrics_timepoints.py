"""Biometrics import follows the project's Timepoints: single -> ses-1, multiple -> the session map."""

import json

import pandas as pd
import pytest

from src.converters.biometrics import convert_biometrics_table_to_prism_dataset
from src.session_map import SessionsNotMappedError, save_session_map


def _convert(tmp_path, rows, timepoints, mapping=None, **kwargs):
    lib = tmp_path / "library"
    lib.mkdir(exist_ok=True)
    (lib / "biometrics-grip.json").write_text(
        json.dumps({"Technical": {"Device": "Grip"}, "Study": {"TaskName": "grip"},
                    "Metadata": {"SchemaVersion": "1.2.0"},
                    "grip_strength": {"Description": "Grip"}})
    )
    src = tmp_path / "in.csv"
    pd.DataFrame(rows).to_csv(src, index=False)
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    if timepoints:
        (out / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": timepoints}}))
    if mapping:
        save_session_map(out, mapping)
    result = convert_biometrics_table_to_prism_dataset(
        input_path=src, library_dir=lib, output_root=out, force=True, **kwargs
    )
    return out, result


def _sessions(out):
    return sorted({p.name for p in out.glob("sub-*/ses-*")})


ROWS = [{"participant_id": "sub-01", "session": "pre", "grip_strength": 40},
        {"participant_id": "sub-02", "session": "post", "grip_strength": 41}]


def test_single_project_writes_ses_1_for_any_label_and_says_so(tmp_path):
    out, result = _convert(tmp_path, ROWS, "single")
    assert _sessions(out) == ["ses-1"]
    assert any("ses-1" in n and "'pre'" in n for n in result.notes)


def test_single_project_without_a_session_column_uses_ses_1(tmp_path):
    out, _ = _convert(tmp_path, [{"participant_id": "sub-01", "grip_strength": 40}], "single")
    assert _sessions(out) == ["ses-1"]


def test_multiple_project_uses_the_map(tmp_path):
    out, _ = _convert(tmp_path, ROWS, "multiple", {"pre": "1", "post": "2"})
    assert _sessions(out) == ["ses-1", "ses-2"]


def test_multiple_project_blocks_an_unmapped_label_before_writing(tmp_path):
    with pytest.raises(SessionsNotMappedError) as info:
        _convert(tmp_path, ROWS, "multiple", {"pre": "1"})
    assert info.value.labels == ["post"]
    assert not list((tmp_path / "out").glob("sub-*"))


def test_no_project_json_keeps_the_label(tmp_path):
    out, _ = _convert(tmp_path, ROWS, None)
    assert _sessions(out) == ["ses-post", "ses-pre"]
