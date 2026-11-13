"""The survey is the layer a stored item map belongs to: two surveys may map the same file codes,
and converting applies only the maps of the surveys being converted."""

import io
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src import item_map  # noqa: E402
from src.converters.survey import convert_survey_file_to_prism_dataset  # noqa: E402
from src.item_map import load_item_map, save_item_map  # noqa: E402
from tests.template_fixtures import dump_complete  # noqa: E402


def _template(items):
    return {i: {"Description": {"en": i}, "Levels": {"1": "low", "2": "high"}} for i in items}


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    library = root / "code" / "library" / "survey"
    library.mkdir(parents=True)
    for task, items in (("ads", ["ADS01", "ADS02"]), ("gad", ["GAD01", "GAD02"])):
        (library / f"survey-{task}.json").write_text(dump_complete(_template(items), task), encoding="utf-8")
    (root / "project.json").write_text(
        json.dumps({"Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]}, "StudyDesign": {"Timepoints": "multiple"}}),
        encoding="utf-8",
    )
    (root / "code" / "session_map.json").write_text(json.dumps({"1": "1"}), encoding="utf-8")
    (tmp_path / "in.csv").write_text("participant_id,Q01,Q02\nsub-001,1,2\nsub-002,2,1\n", encoding="utf-8")
    return root


def _both_maps(project):
    save_item_map(project, "ads", {"ADS01": "Q01", "ADS02": "Q02"}, ["ADS01", "ADS02"])
    save_item_map(project, "gad", {"GAD01": "Q01", "GAD02": "Q02"}, ["GAD01", "GAD02"])


def _convert(project, **kw):
    return convert_survey_file_to_prism_dataset(
        input_path=project.parent / "in.csv", library_dir=project / "code" / "library" / "survey",
        output_root=project, id_column="participant_id", session="1", unknown="ignore",
        force=True, project_path=project, **kw,
    )


def _headers(project):
    return {p.name: p.read_text(encoding="utf-8").splitlines()[0].split("\t")
            for p in sorted(project.glob("sub-*/ses-*/survey/*.tsv"))}


def test_a_two_surveys_mapping_the_same_codes_both_save(project):
    columns = ["participant_id", "Q01", "Q02"]
    item_map.apply_choices(project, "ads", columns, {"ADS01": "Q01", "ADS02": "Q02"}, False)
    # another survey's map does not take the columns away from the guess for this one
    assert "gad" in item_map.tasks_needing_map(project, columns)
    rows = item_map.suggest_for_project(project, "gad", columns)["rows"]
    assert {r["item"]: r["column"] for r in rows} == {"GAD01": "Q01", "GAD02": "Q02"}
    item_map.apply_choices(project, "gad", columns, None, True)
    assert load_item_map(project, "ads") == {"ADS01": "Q01", "ADS02": "Q02"}
    assert load_item_map(project, "gad") == {"GAD01": "Q01", "GAD02": "Q02"}


@pytest.mark.parametrize("survey, kept, gone", [("gad", "GAD01", "ADS01"), ("ads", "ADS01", "GAD01")])
def test_b_only_the_selected_surveys_map_is_applied(project, survey, kept, gone):
    _both_maps(project)
    result = _convert(project, survey=survey)
    assert result.tasks_included == [survey]
    headers = _headers(project)
    assert headers and all(kept in h and gone not in h for h in headers.values())


def test_c_no_survey_selected_and_two_maps_claiming_a_column_stops_before_writing(project):
    _both_maps(project)
    with pytest.raises(ValueError, match="Column 'Q01' is mapped by both ads and gad; select one survey"):
        _convert(project)
    assert not list(project.glob("sub-*"))


def test_d_one_map_and_no_survey_selected_converts_as_before(project):
    save_item_map(project, "ads", {"ADS01": "Q01", "ADS02": "Q02"}, ["ADS01", "ADS02"])
    result = _convert(project)
    assert result.tasks_included == ["ads"]
    assert all("ADS01" in h for h in _headers(project).values())


def _files(project: Path) -> dict[str, str]:
    skip = {"survey_imports.json"}  # the import ledger holds timestamps
    return {
        p.relative_to(project).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(project.rglob("*")) if p.is_file() and p.name not in skip and ".git" not in p.parts
    }


@pytest.mark.parametrize("survey", ["gad", "ads"])
def test_e_the_cli_and_studio_convert_the_selected_survey_alike(project, tmp_path, survey):
    import importlib

    from src.cli.commands.survey import cmd_survey_convert

    _both_maps(project)
    twin = tmp_path / "twin"
    shutil.copytree(project, twin)
    table = project.parent / "in.csv"

    cmd_survey_convert(SimpleNamespace(
        input=str(table), output=str(project), library=None, lang="en", survey=survey, id_column="participant_id",
        session_column=None, run_column=None, session="1", sheet=None, unknown="ignore", dry_run=False, force=None,
        name=None, authors=None, alias=None, project=None, template_versions=None, value_offsets=None,
        archive_sourcedata=False,
    ))

    handlers = importlib.import_module("src.web.blueprints.conversion_survey_handlers")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.add_url_rule("/api/survey-convert", view_func=handlers.api_survey_convert, methods=["POST"])
    with patch.object(handlers, "_resolve_effective_library_path", return_value=twin / "code" / "library"):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["current_project_path"] = str(twin)
            response = client.post(
                "/api/survey-convert",
                data={
                    "file": (io.BytesIO(table.read_bytes()), "in.csv"), "id_column": "participant_id", "session": "1",
                    "language": "en", "save_to_project": "true", "survey": survey, "unknown": "ignore",
                },
                content_type="multipart/form-data",
            )

    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    assert _files(project) == _files(twin)
    assert any(f"task-{survey}" in name for name in _files(twin))
