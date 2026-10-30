"""Every official survey template meets the current survey schema (library relaxation applied)."""

import json
from pathlib import Path

import pytest

from src.prism_template_validation import (
    relax_schema_for_library_template,
    validate_template_against_schema,
    with_default_task_name,
)
from src.schema_manager import load_schema

LIBRARY = Path(__file__).resolve().parents[1] / "official" / "library" / "survey"

FILES = sorted(LIBRARY.glob("survey-*.json"))


@pytest.mark.parametrize("path", FILES, ids=[p.name for p in FILES])
def test_every_official_survey_template_is_a_valid_library_template(path):
    # the file name is the task name, as when the library is loaded
    template = with_default_task_name(json.loads(path.read_text(encoding="utf-8")), path.name, "survey")
    schema = relax_schema_for_library_template(load_schema("survey"))
    errors = validate_template_against_schema(instance=template, schema=schema)
    assert errors == []
