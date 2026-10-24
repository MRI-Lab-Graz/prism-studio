"""Batch import follows the project's Timepoints: single -> ses-1, multiple -> the session map."""

import json
import sys

import numpy as np
import pytest

from src.batch_convert import batch_convert_folder
from src.session_map import save_session_map


@pytest.fixture(autouse=True)
def no_pyedflib(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyedflib", None)


def _project(tmp_path, timepoints):
    out = tmp_path / "out"
    out.mkdir()
    if timepoints:
        (out / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": timepoints}}))
    return out


def _run(tmp_path, make_edf, names, timepoints, mapping=None):
    src = tmp_path / "src"
    src.mkdir()
    for n in names:
        make_edf(src / n, {"ecg": (np.linspace(-1, 1, 8), 4)})
    out = _project(tmp_path, timepoints)
    if mapping:
        save_session_map(out, mapping)
    result = batch_convert_folder(src, out)
    return out, result


def _sessions(out):
    return sorted({p.name for p in out.glob("sub-*/ses-*")})


def test_single_project_writes_ses_1_for_any_label_and_says_so(tmp_path, make_edf):
    out, result = _run(tmp_path, make_edf, ["sub-01_ses-pre_recording-ecg.edf"], "single")
    assert _sessions(out) == ["ses-1"]
    assert any("ses-1" in w and "'pre'" in w for w in result.warnings)


def test_single_project_puts_a_session_less_file_under_ses_1(tmp_path, make_edf):
    out, result = _run(tmp_path, make_edf, ["sub-01_recording-ecg.edf"], "single")
    assert _sessions(out) == ["ses-1"] and result.warnings == []


def test_multiple_project_maps_labels_and_skips_the_unmapped(tmp_path, make_edf):
    out, result = _run(
        tmp_path, make_edf,
        ["sub-01_ses-pre_recording-ecg.edf", "sub-01_ses-post_recording-ecg.edf"],
        "multiple", {"pre": "1"},
    )
    assert _sessions(out) == ["ses-1"]
    assert len(result.skipped) == 1 and "post" in result.skipped[0][1]


def test_no_project_json_keeps_the_filename_session(tmp_path, make_edf):
    out, result = _run(tmp_path, make_edf, ["sub-01_ses-pre_recording-ecg.edf"], None)
    assert _sessions(out) == ["ses-pre"] and result.warnings == []
