"""The survey converter renames file columns by the project's stored item maps (code/item_maps)."""

import io
import json
import os
import sys
from pathlib import Path

import pytest
from flask import Flask, session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.converters.survey import convert_survey_file_to_prism_dataset  # noqa: E402
from src.item_map import save_item_map  # noqa: E402
from tests.template_fixtures import dump_complete  # noqa: E402

ITEMS = ["ADS01", "ADS02"]
TEMPLATE = {i: {"Description": {"en": i}, "Levels": {"1": "low", "2": "high"}} for i in ITEMS}


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    library = root / "code" / "library" / "survey"
    library.mkdir(parents=True)
    (library / "survey-ads.json").write_text(dump_complete(TEMPLATE, "ads"), encoding="utf-8")
    (root / "project.json").write_text(
        json.dumps({"Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]}, "StudyDesign": {"Timepoints": "multiple"}}),
        encoding="utf-8",
    )
    (root / "code" / "session_map.json").write_text(json.dumps({"1": "1"}), encoding="utf-8")
    (tmp_path / "in.csv").write_text("participant_id,A01,A02\nsub-001,1,2\nsub-002,2,1\n", encoding="utf-8")
    return root


def _convert(project, **kw):
    return convert_survey_file_to_prism_dataset(
        input_path=project.parent / "in.csv", library_dir=project / "code" / "library" / "survey",
        output_root=project, id_column="participant_id", session="1", unknown="ignore",
        force=True, project_path=project, **kw,
    )


def _tsv(project):
    return sorted(project.glob("sub-*/ses-*/survey/*task-ads*.tsv"))


def test_without_a_map_the_columns_are_unknown(project):
    with pytest.raises(ValueError, match="A01"):  # no column matches any item: the converter names them
        _convert(project)
    assert not _tsv(project)


def test_with_a_stored_map_the_survey_converts(project):
    save_item_map(project, "ads", {"ADS01": "A01", "ADS02": "A02"}, ITEMS)
    result = _convert(project)
    assert result.tasks_included == ["ads"]
    header = _tsv(project)[0].read_text(encoding="utf-8").splitlines()[0].split("\t")
    assert "ADS01" in header and "ADS02" in header
    assert "A01" not in result.unknown_columns and "A02" not in result.unknown_columns


def test_an_entry_for_a_column_the_file_lacks_is_ignored(project):
    save_item_map(project, "ads", {"ADS01": "A01", "ADS02": "GONE"}, ITEMS)
    result = _convert(project)
    assert result.tasks_included == ["ads"]
    assert "ADS01" in _tsv(project)[0].read_text(encoding="utf-8").splitlines()[0]


def test_two_tasks_claiming_one_column_stops_the_conversion(project):
    save_item_map(project, "ads", {"ADS01": "X1"}, ITEMS)
    save_item_map(project, "other", {"OT01": "X1"}, ["OT01"])
    with pytest.raises(ValueError, match="X1"):
        _convert(project)


def test_the_preview_route_uses_the_stored_map(project):
    import importlib

    from src.web.blueprints.conversion_survey_preview_handlers import handle_api_survey_convert_preview

    handlers = importlib.import_module("src.web.blueprints.conversion_survey_handlers")
    save_item_map(project, "ads", {"ADS01": "A01", "ADS02": "A02"}, ITEMS)
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    with app.test_request_context(
        "/api/survey-convert-preview", method="POST",
        data={"file": (io.BytesIO((project.parent / "in.csv").read_bytes()), "in.csv"), "id_column": "participant_id",
              "session": "1", "unknown": "ignore"},
        content_type="multipart/form-data",
    ):
        session["current_project_path"] = str(project)
        response = handle_api_survey_convert_preview(
            convert_survey_file_to_prism_dataset=handlers.convert_survey_file_to_prism_dataset,
            convert_survey_lsa_to_prism_dataset=handlers.convert_survey_lsa_to_prism_dataset,
            resolve_effective_library_path=lambda: project / "code" / "library",
            run_survey_with_official_fallback=handlers._run_survey_with_official_fallback,
            validate_project_templates_for_tasks=lambda **_kw: [],
            id_column_not_detected_error_cls=handlers.IdColumnNotDetectedError,
        )
        response, status = response if isinstance(response, tuple) else (response, response.status_code)
        payload = response.get_json()
    assert status == 200, payload
    assert "A01" not in json.dumps(payload["preview"].get("unknown_columns", []))
