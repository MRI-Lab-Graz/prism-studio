"""Sidecar validation prepares each schema once per run, not once per data file.

`jsonschema.validate()` checks the schema against its metaschema on every call;
on a 121-subject project that was two thirds of the whole PRISM run.
"""

import json
import os
import sys

import pytest
from jsonschema import Draft7Validator, ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from validator import DatasetValidator

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {"Name": {"type": "string"}},
}


def test_schema_is_checked_once_and_every_sidecar_is_still_validated(tmp_path, monkeypatch):
    checked = []
    monkeypatch.setattr(
        Draft7Validator, "check_schema", classmethod(lambda cls, schema, **kwargs: checked.append(schema))
    )
    validator = DatasetValidator({"survey": SCHEMA})
    folder = tmp_path / "sub-01" / "survey"
    folder.mkdir(parents=True)

    files = []
    for task, name in [("a", "ok"), ("b", 1), ("c", 2)]:
        data = folder / f"sub-01_task-{task}_survey.tsv"
        data.write_text("x\n1\n", encoding="utf-8")
        data.with_suffix(".json").write_text(json.dumps({"Name": name}), encoding="utf-8")
        files.append(str(data))

    errors = [
        [m for level, m in validator.validate_sidecar(f, "survey", str(tmp_path)) if "schema error" in m]
        for f in files
    ]

    assert [len(e) for e in errors] == [0, 1, 1]
    assert "Name: 1 is not of type 'string'" in errors[1][0]
    assert len(checked) == 1


def test_identical_sidecars_are_validated_once(tmp_path, monkeypatch):
    validated = []
    original = Draft7Validator.iter_errors

    def counting(self, instance, *args):
        validated.append(instance)
        return original(self, instance, *args)

    monkeypatch.setattr(Draft7Validator, "iter_errors", counting)
    validator = DatasetValidator()

    for instance in [{"Name": "ok"}, {"Name": "ok"}, {"Name": 1}]:
        try:
            validator._validate_against(instance, SCHEMA)
        except ValidationError:
            pass
    with pytest.raises(ValidationError, match="not of type"):
        validator._validate_against({"Name": 1}, SCHEMA)

    sidecars = ({"Name": "ok"}, {"Name": 1})
    assert [i for i in validated if i in sidecars] == list(sidecars)
