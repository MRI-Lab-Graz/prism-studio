"""The JSON editor's post-save check must agree with the Validate page on dataset_description."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "src" / "json_editor" / "src"))

from backend.json_validator import JSONValidator  # noqa: E402


def test_dataset_description_missing_prism_required_fields_is_reported():
    ok, errors = JSONValidator().validate(
        "dataset_description", {"Name": "x", "BIDSVersion": "1.10.0"}, None
    )

    assert not ok
    text = " ".join(errors)
    assert "Authors" in text and "Keywords" in text and "DatasetType" in text


def test_a_complete_dataset_description_is_valid():
    data = {
        "Name": "A study",
        "BIDSVersion": "1.10.0",
        "DatasetType": "raw",
        "Authors": ["Jane Doe"],
        "Keywords": ["a", "b", "c"],
        "Description": "d" * 60,
        "License": "CC0-1.0",
    }

    ok, errors = JSONValidator().validate("dataset_description", data, None)

    assert errors == [] and ok


def test_flat_participants_json_is_valid():
    data = {"age": {"Description": "Age in years", "Units": "years"}, "sex": {"Description": "Sex"}}

    ok, errors = JSONValidator().validate("participants", data, None)

    assert errors == [] and ok


def test_participants_column_without_description_is_named():
    ok, errors = JSONValidator().validate(
        "participants", {"age": {"Units": "years"}, "sex": {"Description": "Sex"}}, None
    )

    assert not ok
    assert errors == ["Column 'age' missing required 'Description'"]


def test_participants_column_that_is_not_an_object_is_named():
    ok, errors = JSONValidator().validate("participants", {"age": "years"}, None)

    assert not ok
    assert "age" in errors[0]
