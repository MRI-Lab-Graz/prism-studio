"""Validating never changes the dataset: a saved participants_mapping.json is not applied on the way.

Applying a mapping is a conversion (`participants convert`); it used to run silently before every
validation, in the CLI and in Studio, and it needed the full converter, so the PyPI validator
could not do it. Validation only reads.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {"source_column": "participant_id", "standard_variable": "participant_id", "type": "string"},
        "age": {"source_column": "age", "standard_variable": "age", "type": "number"},
    },
}


@pytest.fixture
def study(tmp_path):
    """study/rawdata with a participants.tsv, a saved mapping and a source table that would rewrite it."""
    raw = tmp_path / "study" / "rawdata"
    (raw / "sub-001" / "ses-1" / "survey").mkdir(parents=True)
    (raw / "dataset_description.json").write_text(json.dumps(
        {"Name": "N", "BIDSVersion": "1.10.1", "DatasetType": "raw", "Authors": ["A"]}), encoding="utf-8")
    (raw / "participants.tsv").write_text("participant_id\tage\nsub-001\t99\n", encoding="utf-8")
    (tmp_path / "study" / "code" / "library").mkdir(parents=True)
    (tmp_path / "study" / "code" / "library" / "participants_mapping.json").write_text(json.dumps(MAPPING), encoding="utf-8")
    (tmp_path / "study" / "sourcedata").mkdir()
    (tmp_path / "study" / "sourcedata" / "source.tsv").write_text("participant_id\tage\n001\t25\n", encoding="utf-8")
    return raw


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_command_line_validator_leaves_participants_tsv_alone(study):
    before = _digest(study / "participants.tsv")
    out = subprocess.run(
        [sys.executable, str(ROOT / "app" / "prism.py"), str(study), "--no-bids"],
        capture_output=True, text=True, timeout=300, cwd=ROOT,
    ).stdout

    assert _digest(study / "participants.tsv") == before
    assert "Applied participants mapping" not in out


def test_the_studio_validation_leaves_participants_tsv_alone(study):
    sys.path.insert(0, str(ROOT / "app"))
    from src.web.validation import run_validation

    before = _digest(study / "participants.tsv")
    run_validation(str(study), run_bids=False, run_prism=True)

    assert _digest(study / "participants.tsv") == before
