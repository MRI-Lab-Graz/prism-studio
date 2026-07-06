"""Tests for DatasetFixer._infer_modality(), in particular the eyetracking
suffix hints, which are now sourced from entities.schema.json (via
src/entity_rules.py) instead of a hardcoded, incomplete substring list -
the previous list checked "_eyetrack"/"_eye" but not "_gaze", even though
"_gaze" is a valid eyetracking suffix in the validator's own grammar.
"""

from __future__ import annotations

from pathlib import Path

from src.fixer import DatasetFixer


def _fixer(tmp_path: Path) -> DatasetFixer:
    return DatasetFixer(str(tmp_path), dry_run=True)


def test_infers_eyetracking_from_gaze_suffix(tmp_path: Path) -> None:
    fixer = _fixer(tmp_path)
    filename = "sub-001_task-rest_gaze.tsv"
    assert fixer._infer_modality(filename, filename) == "eyetracking"


def test_infers_eyetracking_from_eyetrack_suffix(tmp_path: Path) -> None:
    fixer = _fixer(tmp_path)
    filename = "sub-001_task-rest_eyetrack.tsv"
    assert fixer._infer_modality(filename, filename) == "eyetracking"


def test_infers_eyetracking_from_eye_suffix(tmp_path: Path) -> None:
    fixer = _fixer(tmp_path)
    filename = "sub-001_task-rest_eye.tsv"
    assert fixer._infer_modality(filename, filename) == "eyetracking"


def test_infers_eyetracking_from_directory(tmp_path: Path) -> None:
    fixer = _fixer(tmp_path)
    file_path = "sub-001/ses-1/eyetracking/sub-001_ses-1_task-rest_gaze.tsv"
    filename = "sub-001_ses-1_task-rest_gaze.tsv"
    assert fixer._infer_modality(file_path, filename) == "eyetracking"


def test_infers_events_survey_biometrics_physio_unchanged(tmp_path: Path) -> None:
    fixer = _fixer(tmp_path)
    assert fixer._infer_modality("x", "sub-001_task-rest_events.tsv") == "events"
    assert fixer._infer_modality("x", "sub-001_survey-panas.tsv") == "survey"
    assert fixer._infer_modality("x", "sub-001_biometrics-hr.tsv") == "biometrics"
    assert fixer._infer_modality("x", "sub-001_task-rest_physio.tsv") == "physio"


def test_infers_unknown_for_unrecognized_file(tmp_path: Path) -> None:
    fixer = _fixer(tmp_path)
    assert fixer._infer_modality("x", "notes.txt") == "unknown"
