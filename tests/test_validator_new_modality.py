"""A new modality is validated from its schema and entity rules alone: no validator code to touch.

Stages the PyPI validator, adds a made-up modality to the staged specification (the way a new
modality arrives with a prism-specification release) and validates data of that modality.
"""

import json

from wheel_helpers import run_validator, stage_wheel


def _add_modality(stage_dir):
    schemas = stage_dir / "prism_validator" / "app" / "schemas" / "stable"
    entities = json.loads((schemas / "entities.schema.json").read_text(encoding="utf-8"))
    entities["modalities"]["olfactory"] = {
        "kind": "prism", "description": "Odour detection tasks", "describedColumns": False,
        "suffixes": ["olfactory"], "extensions": ["tsv", "json"],
    }
    (schemas / "entities.schema.json").write_text(json.dumps(entities), encoding="utf-8")
    (schemas / "olfactory.schema.json").write_text(json.dumps({
        "$schema": "http://json-schema.org/draft-07/schema#", "title": "Olfactory", "type": "object",
        "required": ["Technical"],
        "properties": {"Technical": {"type": "object", "required": ["OdorantSet"], "properties": {"OdorantSet": {"type": "string"}}}},
    }), encoding="utf-8")


def _dataset(root):
    root.mkdir()
    (root / "dataset_description.json").write_text(json.dumps(
        {"Name": "N", "BIDSVersion": "1.10.1", "DatasetType": "raw", "Authors": ["A"]}), encoding="utf-8")
    (root / "participants.tsv").write_text("participant_id\nsub-01\nsub-02\n", encoding="utf-8")
    for sub, sidecar in (("sub-01", {"Technical": {"OdorantSet": "A"}}), ("sub-02", {"Technical": {}})):
        folder = root / sub / "ses-1" / "olfactory"
        folder.mkdir(parents=True)
        (folder / f"{sub}_ses-1_olfactory.tsv").write_text("trial\tresponse\n1\tyes\n", encoding="utf-8")
        (folder / f"{sub}_ses-1_olfactory.json").write_text(json.dumps(sidecar), encoding="utf-8")
    return root


def test_the_wheel_validates_a_modality_it_has_never_seen(tmp_path):
    prism = stage_wheel(tmp_path / "wheel")
    _add_modality(tmp_path / "wheel")

    out = run_validator(prism, _dataset(tmp_path / "proj"), tmp_path).stdout

    assert "olfactory: 4 files" in out  # found and counted as a modality
    assert "sub-02_ses-1_olfactory.json schema error: Technical: 'OdorantSet' is a required property" in out
    assert "sub-01_ses-1_olfactory.json schema error" not in out  # the valid one passes
    assert "olfactory/" in out  # the .bidsignore advice is derived from the modalities too
