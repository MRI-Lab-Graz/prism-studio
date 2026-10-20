"""physio is task-free; the events/ and physiological/ folders are retired."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import runner  # noqa: E402


def _validate(tmp_path, files, sidecar=None, sidecar_for=None):
    for rel in files:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".json"):
            p.write_text(json.dumps((sidecar or {}) if rel in (sidecar_for or ()) else {}))
        else:
            p.write_text("x\n")
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


def test_task_in_physio_hint_names_the_converter(tmp_path):
    errs = _errors(
        _validate(tmp_path, ["sub-01/physio/sub-01_task-x_recording-ecg_physio.edf"])
    )
    assert any("re-convert with destination beh/func/eeg (BIDS .tsv.gz) using the Physio converter" in m for m in errs), errs


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
        sidecar={
            "Technical": {"SamplingFrequency": 100, "StartTime": 0.0, "Columns": ["ecg"]},
            "Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-10-19"},
        },
        sidecar_for=["sub-01/ses-pre/physio/sub-01_ses-pre_recording-ecg_physio.json"],
    )
    # No ERROR/WARNING at all about these files (filename, entities, pattern, ...).
    bad = [(lvl, m) for lvl, m in issues
           if lvl in ("ERROR", "WARNING") and "recording-ecg_physio" in m]
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


import pytest  # noqa: E402


@pytest.mark.parametrize("folder", ["events", "physiological"])
@pytest.mark.parametrize("level", ["sub-01", "sub-01/ses-pre"])
def test_empty_retired_folder_gets_retired_hint(tmp_path, folder, level):
    (tmp_path / level / folder).mkdir(parents=True)
    errs = _errors(_validate(tmp_path, []))
    assert not any("Empty directory" in m and folder in m for m in errs), errs
    hint = "func" if folder == "events" else "physio/"
    assert any(folder in m and hint in m for m in errs), errs


def test_task_hint_attached_to_the_task_message_not_the_first(tmp_path):
    errs = _errors(
        _validate(tmp_path, ["sub-01/physio/sub-01_ses-1_foo-x_task-rest_recording-ecg_physio.edf"])
    )
    hint = "re-convert with destination"
    assert any("task" in m.split(" - task-bound")[0] and hint in m for m in errs), errs
    assert not any("foo" in m.split(" - task-bound")[0] and hint in m for m in errs), errs
