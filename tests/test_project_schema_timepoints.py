"""project.json schemas declare StudyDesign.Timepoints (single | multiple)."""

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMAS = Path(__file__).resolve().parents[1] / "app" / "schemas"


def study_design_schema(version):
    schema = json.loads((SCHEMAS / version / "project.schema.json").read_text(encoding="utf-8"))
    return schema["properties"]["StudyDesign"]


@pytest.mark.parametrize("version", ["stable", "v0.2"])
@pytest.mark.parametrize("value", ["single", "multiple"])
def test_declared_timepoints_are_valid(version, value):
    jsonschema.validate({"Timepoints": value}, study_design_schema(version))


@pytest.mark.parametrize("version", ["stable", "v0.2"])
@pytest.mark.parametrize("value", ["sometimes", "", "Multiple", 2])
def test_any_other_timepoints_value_is_rejected(version, value):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"Timepoints": value}, study_design_schema(version))
