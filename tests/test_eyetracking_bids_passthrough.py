import os
import sys
import tempfile
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.fixer import DatasetFixer
from src.validator import BIDS_MODALITIES, PRISM_MODALITIES, DatasetValidator


def test_eyetracking_is_bids_passthrough_not_prism() -> None:
    assert "eyetracking" in BIDS_MODALITIES
    assert "eyetracking" not in PRISM_MODALITIES


def test_validator_skips_prism_sidecar_requirements_for_eyetracking() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_file = root / "sub-01" / "eyetracking" / "sub-01_task-gaze_eyetrack.tsv"
        data_file.parent.mkdir(parents=True, exist_ok=True)
        data_file.write_text("timestamp\tx_coordinate\ty_coordinate\n0\t1\t2\n", encoding="utf-8")

        validator = DatasetValidator({})
        issues = validator.validate_sidecar(str(data_file), "eyetracking", str(root))

        assert issues == []


def test_fixer_does_not_create_eyetracking_prism_sidecar_stubs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_file = (
            root
            / "sub-01"
            / "ses-01"
            / "eyetracking"
            / "sub-01_ses-01_task-gaze_eyetrack.tsv"
        )
        data_file.parent.mkdir(parents=True, exist_ok=True)
        data_file.write_text("timestamp\tx_coordinate\ty_coordinate\n0\t1\t2\n", encoding="utf-8")

        fixer = DatasetFixer(str(root))
        fixes = fixer.analyze()

        prism201_eye_fixes = [
            fix
            for fix in fixes
            if fix.issue_code == "PRISM201"
            and "eyetrack" in (fix.description or "").lower()
        ]
        assert prism201_eye_fixes == []
