"""Optional Preregistration block in project.json: schema, save path, GUI wiring."""

import json
import re
import sys
from pathlib import Path

import jsonschema
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))

SCHEMA = json.loads(
    (REPO / "app/schemas/stable/project.schema.json").read_text(encoding="utf-8")
)

FULL_BLOCK = {
    "DataStatus": "not-collected",
    "Hypotheses": ["H1: Mindfulness lowers stress.", "H2: Effect lasts 4 weeks."],
    "PrimaryOutcomes": "PSS-10 total score at post-test",
    "SecondaryOutcomes": "WHO-5 total score",
    "AnalysisPlan": "ANCOVA on post-test PSS with baseline as covariate",
    "InferenceCriteria": "alpha = .05, one-sided, Holm correction",
    "ExploratoryAnalyses": "Moderation by age",
}


def prereg_schema():
    return SCHEMA["properties"]["Preregistration"]


def test_full_block_is_valid():
    jsonschema.validate(FULL_BLOCK, prereg_schema())


def test_block_is_optional():
    assert "Preregistration" not in SCHEMA.get("required", [])


def test_unknown_key_is_rejected():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"Hypothesis": "typo"}, prereg_schema())


@pytest.mark.parametrize("value", ["collected", "", "Not-Collected"])
def test_unknown_data_status_is_rejected(value):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"DataStatus": value}, prereg_schema())


def test_study_metadata_save_persists_block(tmp_path):
    from flask import Flask

    from src.web.blueprints import projects_metadata_helpers as helpers
    from src.web.blueprints.projects_study_metadata_handlers import (
        handle_save_study_metadata,
    )

    (tmp_path / "project.json").write_text(json.dumps({"Metadata": {}}))

    class _PM:
        def update_citation_cff(self, *a, **k):
            return None

    with Flask(__name__).test_request_context(
        "/api/projects/study-metadata",
        method="POST",
        json={"Preregistration": FULL_BLOCK},
    ):
        handle_save_study_metadata(
            get_current_project=lambda: {"path": str(tmp_path)},
            read_project_json=helpers._read_project_json,
            write_project_json=helpers._write_project_json,
            get_bids_file_path=lambda p, f: p / f,
            editable_sections=helpers._EDITABLE_SECTIONS,
            compute_methods_completeness=lambda d, dd: {"score": 0},
            project_manager=_PM(),
        )

    saved = json.loads((tmp_path / "project.json").read_text())
    assert saved["Preregistration"] == FULL_BLOCK


def test_create_project_keeps_block():
    from src.project_manager import ProjectManager

    meta = ProjectManager()._create_project_metadata(
        "demo", {"Preregistration": FULL_BLOCK}
    )
    assert meta["Preregistration"] == FULL_BLOCK


def test_create_route_forwards_block():
    src = (REPO / "app/src/web/blueprints/projects_lifecycle_handlers.py").read_text()
    assert '"Preregistration": data.get("Preregistration")' in src


@pytest.mark.parametrize("field", sorted(prereg_schema()["properties"]))
def test_every_field_has_a_form_input_that_is_loaded_and_saved(field):
    """Each schema field needs an input on the Projects page, and both the
    edit (metadata.js) and create (create-project.js) payloads must send it."""
    field_id = f"smPrereg{field}"
    template = (
        REPO / "app/templates/includes/projects/study_metadata.html"
    ).read_text()
    assert re.search(rf'id="{field_id}"', template), f"no input #{field_id}"

    metadata_js = (REPO / "app/static/js/modules/projects/metadata.js").read_text()
    create_js = (REPO / "app/static/js/modules/projects/create-project.js").read_text()
    # loaded into the form + written into the save payload
    assert metadata_js.count(f"'{field_id}'") >= 2, f"{field_id} not loaded/saved"
    assert f"'{field_id}'" in create_js, f"{field_id} not sent on create"
