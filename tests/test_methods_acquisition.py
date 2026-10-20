"""acquisition_summary: counts and sidecar parameters per modality."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "app"))

from src.methods_acquisition import acquisition_summary  # noqa: E402

SIDECAR = {
    "RepetitionTime": 2.0,
    "EchoTime": 0.03,
    "FlipAngle": 90,
    "MagneticFieldStrength": 3,
    "Manufacturer": "Siemens",
    "ManufacturersModelName": "Prisma",
}


def _sidecar(root, sub, ses, modality, data=SIDECAR):
    d = root / sub / ses / modality
    d.mkdir(parents=True)
    (d / f"{sub}_{ses}_task-rest_bold.json").write_text(json.dumps(data), encoding="utf-8")


def test_session_labels_are_not_merged(tmp_path):
    _sidecar(tmp_path, "sub-01", "ses-1", "func")
    _sidecar(tmp_path, "sub-02", "ses-01", "func")
    func = acquisition_summary(tmp_path)["modalities"]["func"]
    assert func["n_subjects"] == 2
    assert func["sessions"] == {"1": 1, "01": 1}


def test_sidecar_values_are_surfaced(tmp_path):
    _sidecar(tmp_path, "sub-01", "ses-1", "func")
    _sidecar(tmp_path, "sub-02", "ses-1", "func", {**SIDECAR, "RepetitionTime": 2.5})
    params = acquisition_summary(tmp_path)["modalities"]["func"]["params"]
    assert params["RepetitionTime"] == [2.0, 2.5]
    assert params["Manufacturer"] == ["Siemens"]


def test_rawdata_folder_is_used(tmp_path):
    _sidecar(tmp_path / "rawdata", "sub-01", "ses-1", "anat")
    assert "anat" in acquisition_summary(tmp_path)["modalities"]


def test_empty_tree(tmp_path):
    assert acquisition_summary(tmp_path) == {"modalities": {}}


def test_survey_sidecars_are_not_acquisition(tmp_path):
    _sidecar(tmp_path, "sub-01", "ses-1", "survey", {"Study": {}})
    assert acquisition_summary(tmp_path) == {"modalities": {}}
