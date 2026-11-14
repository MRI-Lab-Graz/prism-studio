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


def test_every_official_survey_template_declares_the_current_major_schema_version():
    from src.modality_versions import current_survey_schema_version
    from src.schema_manager import parse_version

    current = current_survey_schema_version()
    stale = {
        p.name: v
        for p in FILES
        if parse_version(v := json.loads(p.read_text(encoding="utf-8")).get("Metadata", {}).get("SchemaVersion"))[0]
        != parse_version(current)[0]
    }
    assert stale == {}, f"templates not at survey schema major {current}: {sorted(stale)}"
