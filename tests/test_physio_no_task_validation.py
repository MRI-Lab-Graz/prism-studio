"""physio is task-free; the events/ and physiological/ folders are retired."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import runner  # noqa: E402


def _validate(tmp_path, files):
    for rel in files:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({}) if rel.endswith(".json") else "x\n")
    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": "1.9.0"})
    )
    issues, _ = runner.validate_dataset(str(tmp_path), run_prism=True, run_bids=False)
    return [(lvl, msg) for lvl, msg, *_ in issues]


def _errors(issues):
    return [m for lvl, m in issues if lvl == "ERROR"]


def test_events_folder_is_flagged(tmp_path):
    errs = _errors(_validate(tmp_path, ["sub-01/events/sub-01_task-x_events.tsv"]))
    assert any("events" in m and "func" in m for m in errs), errs


def test_physiological_folder_is_flagged(tmp_path):
    errs = _errors(
        _validate(tmp_path, ["sub-01/physiological/sub-01_recording-ecg_physio.edf"])
    )
    assert any("physiological" in m and "physio/" in m for m in errs), errs


def test_task_in_physio_filename_is_error(tmp_path):
    errs = _errors(
        _validate(tmp_path, ["sub-01/physio/sub-01_task-x_recording-ecg_physio.edf"])
    )
    assert any("beh" in m and "func" in m and "eeg" in m for m in errs), errs


def test_task_in_physio_sidecar_is_error(tmp_path):
    errs = _errors(
        _validate(tmp_path, ["sub-01/physio/sub-01_task-x_recording-ecg_physio.json"])
    )
    assert any("beh" in m and "func" in m and "eeg" in m for m in errs), errs


def test_task_free_physio_is_clean(tmp_path):
    issues = _validate(
        tmp_path,
        [
            "sub-01/ses-pre/physio/sub-01_ses-pre_recording-ecg_physio.edf",
            "sub-01/ses-pre/physio/sub-01_ses-pre_recording-ecg_physio.json",
        ],
    )
    bad = [m for m in _errors(issues) if "sub-01_ses-pre_recording-ecg_physio" in m
           and ("entity" in m or "filename" in m.lower() or "pattern" in m)]
    assert bad == []


def test_events_tsv_in_func_still_checked(tmp_path):
    issues = _validate(tmp_path, ["sub-01/func/sub-01_task-x_events.tsv"])
    assert not any("is not a PRISM modality" in m for m in _errors(issues))
    assert any("sidecar" in m.lower() for _, m in issues), issues


def test_events_folder_at_session_level_is_flagged(tmp_path):
    errs = _errors(
        _validate(tmp_path, ["sub-01/ses-pre/events/sub-01_ses-pre_task-x_events.tsv"])
    )
    assert any("events" in m and "func" in m for m in errs), errs


def test_physiological_folder_at_session_level_is_flagged(tmp_path):
    errs = _errors(
        _validate(
            tmp_path,
            ["sub-01/ses-pre/physiological/sub-01_ses-pre_recording-ecg_physio.edf"],
        )
    )
    assert any("physiological" in m and "physio/" in m for m in errs), errs
