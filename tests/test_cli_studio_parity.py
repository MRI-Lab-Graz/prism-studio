"""Studio only triggers what the CLI runs: the same input must give the same files in both.

Each test runs the CLI command and Studio's adapter on identical copies of a project and compares
what they write. A difference is a bug in one of the two paths, never a feature.
"""

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import config
from tests.template_fixtures import complete

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import src.cli.commands.survey as survey_cli  # noqa: E402
from src.cli.commands.survey import cmd_survey_convert  # noqa: E402

TEMPLATE_I18N = complete({
    "I18n": {"DefaultLanguage": "de"},
    "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "de"},
    "Study": {"TaskName": "pss", "OriginalName": "pss", "LicenseID": "Other", "License": ""},
    "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2026-10-01", "Creator": "t"},
    "PSS1": {
        "Description": {"de": "Frage", "en": "Question"},
        "Levels": {"0": {"de": "nie", "en": "never"}, "1": {"de": "oft", "en": "often"}},
    },
}, "pss")
READY_PROJECT = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "single"},
}


@pytest.fixture
def world(tmp_path):
    project = tmp_path / "proj"
    library = project / "code" / "library" / "survey"
    library.mkdir(parents=True)
    (library / "survey-pss.json").write_text(json.dumps(TEMPLATE_I18N), encoding="utf-8")
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    table = tmp_path / "pss.csv"
    table.write_text("ID,PSS1\nsub-001,0\nsub-002,1\n", encoding="utf-8")
    return project, table


def _cli_args(project, table, **overrides):
    args = dict(
        input=str(table), output=str(project), library=None, lang="en", survey=None, id_column="ID",
        session_column=None, run_column=None, sheet=None, unknown="ignore", dry_run=False, force=True,
        name=None, authors=None, alias=None, project=None, template_versions=None, value_offsets=None,
    )
    args.update(overrides)
    return SimpleNamespace(**args)


def _studio_convert(project, table, **overrides):
    """What Studio's Convert button runs (its adapter around the same backend converter)."""
    from src.converters.survey import convert_survey_file_to_prism_dataset
    from src.web.blueprints.conversion_survey_handlers import _run_survey_with_official_fallback

    kwargs = dict(
        input_path=table, output_root=project, survey=None, id_column="ID", session_column=None, session=None,
        unknown="ignore", dry_run=False, force=True, language="en", skip_participants=True,
    )
    kwargs.update(overrides)
    return _run_survey_with_official_fallback(
        convert_survey_file_to_prism_dataset,
        library_dir=str(project / "code" / "library" / "survey"),
        fallback_project_path=str(project),
        **kwargs,
    )


def _written(project: Path) -> dict[str, str]:
    """Every file a conversion leaves in the project: name -> content."""
    wanted = ["task-*_survey.json", "code/library/survey/*.json", "sub-*/ses-*/survey/*.tsv", "participants.*"]
    return {
        str(p.relative_to(project)): p.read_text(encoding="utf-8")
        for pattern in wanted
        for p in sorted(project.glob(pattern))
    }


def test_the_cli_leaves_language_maps_to_the_converter(world, monkeypatch, capsys):
    """One place turns a multilingual template into one language: the converter, for CLI and Studio alike."""
    project, table = world

    def forbidden(*args, **kwargs):
        raise AssertionError("the CLI compiled the language maps itself")

    monkeypatch.setattr(survey_cli, "compile_survey_template", forbidden)
    cmd_survey_convert(_cli_args(project, table))

    assert "Survey conversion complete" in capsys.readouterr().out
    sidecar = json.loads((project / "task-pss_survey.json").read_text(encoding="utf-8"))
    assert sidecar["PSS1"]["Description"] == "Question"  # English was asked for
    assert sidecar["Technical"]["Language"] == "en"  # and the sidecar says so


def test_the_cli_and_studio_write_the_same_files(world, tmp_path, capsys):
    project, table = world
    twin = tmp_path / "twin"
    shutil.copytree(project, twin)

    cmd_survey_convert(_cli_args(project, table))
    _studio_convert(twin, table)

    cli_files, studio_files = _written(project), _written(twin)
    assert cli_files.keys() == studio_files.keys()
    assert cli_files == studio_files


def test_a_dry_run_leaves_the_same_files_in_the_cli_and_in_studio(world, tmp_path, monkeypatch, capsys):
    """Studio's preview puts the templates it used into the project (its template check reads them there);
    the CLI's dry-run does the same, and neither writes data."""
    project, table = world
    mine = tmp_path / "mine"
    (mine / "survey").mkdir(parents=True)
    shutil.move(str(project / "code" / "library" / "survey" / "survey-pss.json"), str(mine / "survey" / "survey-pss.json"))
    monkeypatch.setattr(config, "load_app_settings", lambda app_root=None: config.AppSettings(personal_library_path=str(mine)))
    twin = tmp_path / "twin"
    shutil.copytree(project, twin)

    cmd_survey_convert(_cli_args(project, table, dry_run=True))
    _studio_convert(twin, table, dry_run=True)

    cli_files, studio_files = _written(project), _written(twin)
    assert list(cli_files) == ["code/library/survey/survey-pss.json"]  # the copy, and no data
    assert cli_files == studio_files


def test_saving_a_template_writes_the_same_file_in_the_cli_and_in_studio(tmp_path):
    import importlib
    import os

    from flask import Flask, session
    from template_fixtures import project_template

    from src.cli.commands.library import cmd_library_template_save

    app_dir = Path(__file__).resolve().parents[1] / "app"
    handlers = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(app_dir))
    app.secret_key = os.urandom(32)
    template = project_template("mood")
    source = tmp_path / "mood.json"
    source.write_text(json.dumps(template), encoding="utf-8")
    cli_project, studio_project = tmp_path / "cli", tmp_path / "studio"
    cli_project.mkdir()
    studio_project.mkdir()

    cmd_library_template_save(SimpleNamespace(
        project=str(cli_project), to="project", modality="survey", filename="survey-mood.json", template=str(source),
        schema_version="stable", is_global=False, force=False,
    ))
    with app.test_request_context(
        "/api/template-editor/save", method="POST",
        json={"modality": "survey", "schema_version": "stable", "filename": "survey-mood.json", "template": template},
    ):
        session["current_project_path"] = str(studio_project)
        _response, status = handlers.api_template_editor_save()

    assert status == 200
    name = "code/library/survey/survey-mood.json"
    # parsed, not bytes: Flask's test client sorts the keys of the JSON it sends
    assert json.loads((cli_project / name).read_text(encoding="utf-8")) == json.loads((studio_project / name).read_text(encoding="utf-8"))


def test_saving_strips_and_warns_the_same_in_the_cli_and_in_studio(tmp_path, capsys):
    import importlib
    import os

    from flask import Flask, session
    from template_fixtures import project_template

    from src.cli.commands.library import cmd_library_template_save

    app_dir = Path(__file__).resolve().parents[1] / "app"
    handlers = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(app_dir))
    app.secret_key = os.urandom(32)
    template = project_template("mood")
    template["Technical"]["Respondent"] = ""
    item = next(k for k, v in template.items() if isinstance(v, dict) and "Description" in v)
    template[item]["LimeSurvey"] = {"questionType": "L", "inputWidth": "30", "columnName": "q1"}
    source = tmp_path / "mood.json"
    source.write_text(json.dumps(template), encoding="utf-8")
    cli_project, studio_project = tmp_path / "cli", tmp_path / "studio"
    cli_project.mkdir()
    studio_project.mkdir()

    cmd_library_template_save(SimpleNamespace(
        project=str(cli_project), to="project", modality="survey", filename="survey-mood.json", template=str(source),
        schema_version="stable", is_global=False, force=False,
    ))
    printed = capsys.readouterr().out
    with app.test_request_context(
        "/api/template-editor/save", method="POST",
        json={"modality": "survey", "schema_version": "stable", "filename": "survey-mood.json", "template": template},
    ):
        session["current_project_path"] = str(studio_project)
        response, status = handlers.api_template_editor_save()

    assert status == 200
    body = response.get_json()
    name = "code/library/survey/survey-mood.json"
    cli_saved = json.loads((cli_project / name).read_text(encoding="utf-8"))
    assert cli_saved == json.loads((studio_project / name).read_text(encoding="utf-8"))
    assert cli_saved[item]["LimeSurvey"] == {"columnName": "q1"}
    assert body["removed"] == [f"{item}: inputWidth, questionType"]
    assert {"path": "Technical/Respondent", "message": "Technical/Respondent is missing", "severity": "error"} in body["missing"]
    for field in body["missing"]:
        assert f"warning: {field['message']}" in printed
    assert "removed LimeSurvey export settings from 1 items" in printed


OLD_LS_TEMPLATE = complete({
    "Study": {"OriginalName": "Old"},
    "I18n": {"Languages": ["de"], "DefaultLanguage": "de"},
    "q1": {
        "Description": {"de": "Frage eins"},
        "Levels": {str(i): {"de": f"Stufe {i}"} for i in range(1, 5)},
        "LimeSurvey": {"mandatory": False, "questionType": "!", "helpText": "h", "inputWidth": "30"},
    },
    "q2": {"Description": {"de": "Gewicht"}, "DataType": "integer"},
}, "old")


def _studio_response_bytes(handler, json_body):
    """Run a Studio export route in a request context; return the file it sends."""
    import os

    from flask import Flask

    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    with app.test_request_context("/", method="POST", json=json_body):
        response = handler()
        if isinstance(response, tuple):
            raise AssertionError(response[0].get_json())
        response.direct_passthrough = False
        return response.get_data()


def test_customized_limesurvey_export_writes_the_same_file_in_the_cli_and_in_studio(tmp_path, capsys):
    from src.cli.commands.survey import cmd_survey_customizer_groups, cmd_survey_export_lss_customized
    from src.web.blueprints.tools_survey_customizer_handlers import (
        handle_survey_customizer_export,
        handle_survey_customizer_load,
    )
    from src.template_info import detect_languages_from_template

    template = tmp_path / "survey-old.json"
    template.write_text(json.dumps(OLD_LS_TEMPLATE), encoding="utf-8")

    # loading: the CLI's customizer-groups and Studio's load give the same groups (ids are fresh uuids)
    cli_groups_file = tmp_path / "groups.json"
    cmd_survey_customizer_groups(SimpleNamespace(template=[str(template)], runs=1, language="de", output=str(cli_groups_file)))
    cli_groups = json.loads(cli_groups_file.read_text(encoding="utf-8"))["groups"]
    studio_body = _studio_response_bytes(
        lambda: handle_survey_customizer_load(
            {"files": [{"path": str(template)}], "language": "de"}, detect_languages_from_template
        ),
        {},
    )
    studio_groups = json.loads(studio_body)["groups"]

    def without_ids(groups):
        return [{**g, "id": None, "questions": [{**q, "id": None} for q in g["questions"]]} for g in groups]

    assert without_ids(cli_groups) == without_ids(studio_groups)
    assert [q["questionType"] for q in cli_groups[0]["questions"]] == ["L", "N"]

    # exporting: one override for this export, same .lss
    cli_groups[0]["questions"][0]["toolOverrides"] = {"questionType": "!"}
    ls_settings = {"showProgress": "N"}
    customization = tmp_path / "customization.json"
    customization.write_text(
        json.dumps({"groups": cli_groups, "survey_title": "Old survey", "ls_settings": ls_settings}), encoding="utf-8"
    )
    cli_out = tmp_path / "cli.lss"
    cmd_survey_export_lss_customized(SimpleNamespace(
        customization_json=str(customization), output=str(cli_out), language="de", languages="de",
        base_language="de", no_matrix=False, no_matrix_global=False, survey_title=None,
    ))
    studio_lss = _studio_response_bytes(
        lambda: handle_survey_customizer_export(
            {
                "exportFormat": "limesurvey",
                "survey": {"title": "Old survey", "language": "de", "languages": ["de"], "base_language": "de"},
                "groups": cli_groups,
                "exportOptions": {"matrix": True, "matrix_global": True},
                "lsSettings": ls_settings,
            },
            str(tmp_path),
        ),
        {},
    )
    assert cli_out.read_bytes() == studio_lss
    assert b"<type><![CDATA[!]]></type>" in studio_lss or b"<type>!</type>" in studio_lss
    assert json.loads(template.read_text(encoding="utf-8")) == OLD_LS_TEMPLATE  # the override stays in the export


def test_quick_limesurvey_export_writes_the_same_file_in_the_cli_and_in_studio(tmp_path, capsys):
    from src.cli.commands.survey import cmd_survey_export_lss
    from src.web.blueprints.tools_generation_handlers import handle_generate_lss_endpoint

    template = tmp_path / "survey-old.json"
    template.write_text(json.dumps(OLD_LS_TEMPLATE), encoding="utf-8")
    cli_out = tmp_path / "cli.lss"
    cmd_survey_export_lss(SimpleNamespace(
        files=[str(template)], output=str(cli_out), language="de", languages="de", base_language="de",
        matrix=True, matrix_global=True, include=None,
    ))
    studio_lss = _studio_response_bytes(
        handle_generate_lss_endpoint,
        {"files": [{"path": str(template)}], "language": "de", "languages": ["de"], "base_language": "de",
         "matrix": True, "matrix_global": True},
    )
    assert cli_out.read_bytes() == studio_lss


@pytest.mark.parametrize("damage", ["none", "required-field-gone", "language-missing"])
def test_validating_a_template_answers_the_same_in_the_cli_and_in_studio(tmp_path, capsys, damage):
    import importlib
    import os

    from flask import Flask
    from template_fixtures import project_template

    from src.cli.commands.library import cmd_library_template_validate

    template = project_template("mood")
    if damage == "required-field-gone":
        del template["Study"]["TaskName"]
    if damage == "language-missing":
        item = next(k for k, v in template.items() if isinstance(v, dict) and isinstance(v.get("Description"), dict))
        template[item]["Description"] = {"en": "Question"}
        template["I18n"] = {"DefaultLanguage": "en", "Languages": ["en", "de"]}
    source = tmp_path / "mood.json"
    source.write_text(json.dumps(template), encoding="utf-8")

    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.register_blueprint(importlib.import_module("src.web.blueprints.tools_template_editor_blueprint").tools_template_editor_bp)
    studio = app.test_client().post(
        "/api/template-editor/validate", json={"modality": "survey", "schema_version": "stable", "template": template}
    ).get_json()

    code = 0
    try:
        cmd_library_template_validate(SimpleNamespace(
            template=str(source), modality="survey", schema_version="stable", is_global=False, json=True,
        ))
    except SystemExit as exc:
        code = exc.code
    assert json.loads(capsys.readouterr().out) == studio
    assert code == (0 if studio["ok"] else 1)


def _two_projects(tmp_path):
    """Two identical projects: one for the command, one for Studio."""
    projects = []
    for name in ("cli", "studio"):
        root = tmp_path / name / "study"  # same folder name: the fixer puts it into the files it creates
        root.mkdir(parents=True)
        (root / "project.json").write_text(json.dumps({
            "Basics": {"Name": "Parity", "Authors": ["Lovelace, Ada"], "Keywords": ["a", "b", "c"], "Description": "A study."},
            "StudyDesign": {"Timepoints": "single"},
        }), encoding="utf-8")
        (root / "dataset_description.json").write_text(
            json.dumps({"Name": "Parity", "BIDSVersion": "1.10.0", "DatasetType": "raw", "Authors": ["Lovelace, Ada"], "Keywords": ["a", "b", "c"]}), encoding="utf-8"
        )
        projects.append(root)
    return projects


def _studio_handler(handler, project, **kwargs):
    from flask import Flask

    with Flask(__name__).test_request_context(method="POST", json={"project_path": str(project)}):
        response = handler(**kwargs)
    response, status = (response, 200) if not isinstance(response, tuple) else response
    return response.get_json(), status


def test_generating_the_readme_writes_the_same_file_in_the_cli_and_in_studio(tmp_path, capsys):
    from src.cli.commands.project import cmd_project_generate_readme
    from src.web.blueprints.projects_study_metadata_handlers import handle_generate_readme

    cli, studio = _two_projects(tmp_path)
    cmd_project_generate_readme(SimpleNamespace(project=str(cli)))
    body, status = _studio_handler(handle_generate_readme, studio, get_current_project=lambda: {})

    assert status == 200 and body["success"]
    assert (cli / "README.md").read_text(encoding="utf-8") == (studio / "README.md").read_text(encoding="utf-8")
    assert body["message"] in capsys.readouterr().out


def test_regenerating_the_citation_writes_the_same_file_in_the_cli_and_in_studio(tmp_path, capsys):
    from src.cli.commands.project import cmd_project_regenerate_citation
    from src.project_manager import ProjectManager
    from src.web.blueprints.projects_description_handlers import handle_regenerate_citation

    cli, studio = _two_projects(tmp_path)
    for root in (cli, studio):  # legacy files Studio removes while regenerating
        (root / "contributors.json").write_text("{}", encoding="utf-8")
    cmd_project_regenerate_citation(SimpleNamespace(project=str(cli)))
    body, status = _studio_handler(
        handle_regenerate_citation, studio,
        get_current_project=lambda: {}, get_bids_file_path=None, project_manager=ProjectManager(),
    )

    assert status == 200 and body["success"]
    # date-released is the day of writing: compare the rest
    strip = lambda p: [l for l in (p / "CITATION.cff").read_text(encoding="utf-8").splitlines() if not l.startswith("date-released")]
    assert strip(cli) == strip(studio)
    assert not (cli / "contributors.json").exists() and not (studio / "contributors.json").exists()
    assert body["message"] in capsys.readouterr().out


def _unfixed_projects(tmp_path):
    cli, studio = _two_projects(tmp_path)
    for root in (cli, studio):
        (root / "dataset_description.json").unlink()  # PRISM001: the fixer creates it
    return cli, studio


def _studio_json(handler, body, **kwargs):
    from flask import Flask

    with Flask(__name__).test_request_context(method="POST", json=body):
        response = handler(**kwargs)
    response, status = (response, 200) if not isinstance(response, tuple) else response
    return response.get_json(), status


def _tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in sorted(root.rglob("*")) if p.is_file()}


def test_listing_fixable_issues_answers_the_same_in_the_cli_and_in_studio(tmp_path, capsys):
    from src.cli.commands.project import cmd_project_fixable
    from src.project_manager import ProjectManager
    from src.web.blueprints.projects_lifecycle_handlers import handle_get_fixable_issues

    cli, studio = _unfixed_projects(tmp_path)
    cmd_project_fixable(SimpleNamespace(project=str(cli), json=True))
    body, status = _studio_json(handle_get_fixable_issues, {"path": str(studio)}, project_manager=ProjectManager())

    cli_issues = json.loads(capsys.readouterr().out)
    assert status == 200 and body["issues"]
    # the paths differ per project folder: compare with the folder name taken out
    norm = lambda issues, root: json.loads(json.dumps(issues).replace(str(root), "<root>"))
    assert norm(cli_issues, cli) == norm(body["issues"], studio)


def test_applying_fixes_writes_the_same_files_in_the_cli_and_in_studio(tmp_path, capsys):
    from src.cli.commands.project import cmd_project_fix
    from src.project_manager import ProjectManager
    from src.web.blueprints.projects_lifecycle_handlers import handle_fix_project

    cli, studio = _unfixed_projects(tmp_path)
    cmd_project_fix(SimpleNamespace(project=str(cli), codes="PRISM001", json=True))
    body, status = _studio_json(handle_fix_project, {"path": str(studio), "fix_codes": ["PRISM001"]}, project_manager=ProjectManager())

    assert status == 200 and body["success"] and body["count"] >= 1
    assert json.loads(capsys.readouterr().out)["count"] == body["count"]
    assert _tree(cli) == _tree(studio)
    assert (cli / "dataset_description.json").exists()


def test_the_methods_boilerplate_is_the_same_text_in_the_cli_and_in_studio(tmp_path):
    from template_fixtures import project_template

    from src.cli.commands.library import cmd_library_generate_methods_text
    from src.web.blueprints.tools_generation_handlers import handle_generate_boilerplate_endpoint

    library = tmp_path / "library" / "survey"
    library.mkdir(parents=True)
    template_file = library / "survey-mood.json"
    template_file.write_text(json.dumps(project_template("mood")), encoding="utf-8")
    out = tmp_path / "methods.md"

    cmd_library_generate_methods_text(SimpleNamespace(survey_lib=str(library), biometrics_lib=None, output=str(out), lang="en"))
    body, status = _studio_json(handle_generate_boilerplate_endpoint, {"files": [str(template_file)], "language": "en"})

    assert status == 200
    assert out.read_text(encoding="utf-8") == body["md"]
    assert "PRISM schema version" in body["md"]


def test_the_merge_conflict_report_is_the_same_csv_in_the_cli_and_in_studio(tmp_path, capsys):
    import io
    from unittest.mock import patch

    from flask import Flask

    from src.cli.commands.participants import cmd_participants_merge
    from src.web.blueprints import conversion_participants_mapping as mapping_module
    from src.web.blueprints.conversion_participants_blueprint import conversion_participants_bp

    project = tmp_path / "study"
    project.mkdir()
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    (project / "participants.tsv").write_text("participant_id\tage\tsex\nsub-001\t21\tF\nsub-002\t22\tM\n", encoding="utf-8")
    table = b"participant_id,age,sex\nsub-001,25,F\nsub-002,22,X\n"
    source = tmp_path / "participants.csv"
    source.write_bytes(table)

    app = Flask(__name__)
    app.secret_key = "t"
    app.register_blueprint(conversion_participants_bp)
    with patch.object(mapping_module, "_load_survey_template_item_ids", return_value=set()), patch.object(
        mapping_module, "resolve_effective_library_path", return_value=project
    ):
        client = app.test_client()
        with client.session_transaction() as flask_session:
            flask_session["current_project_path"] = str(project)
        response = client.post(
            "/api/participants-merge-conflicts",
            data={"separator": "comma", "id_column": "participant_id", "preview_limit": "1", "file": (io.BytesIO(table), "participants.csv")},
            content_type="multipart/form-data",
        )
        cmd_participants_merge(SimpleNamespace(
            project=str(project), input=str(source), separator="comma", sheet=0, preview_limit=1, id_column="participant_id",
            conflicts_csv=True, apply=False, json=False, screening_only=None, neurobagel_schema=None,
            session_resolution=None, harmonization=None, sessions_from_date=None,
        ))

    assert response.status_code == 200
    cli_csv = capsys.readouterr().out
    assert cli_csv == response.data.decode("utf-8")
    assert "sub-001" in cli_csv and "sub-002" in cli_csv  # both conflicts, though preview_limit is 1


@pytest.mark.parametrize("data", [{"Name": "x", "BIDSVersion": "1.10.0"}, {"Name": 5}], ids=["valid", "wrong-type"])
def test_the_json_editor_validates_the_same_in_the_cli_and_in_studio(tmp_path, capsys, data):
    from flask import Flask

    from src.cli.commands.json_editor import cmd_json_editor_validate
    from src.json_editor_blueprint import create_json_editor_blueprint

    source = tmp_path / "dataset_description.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    app = Flask(__name__)
    app.register_blueprint(create_json_editor_blueprint(bids_folder=None))
    response = app.test_client().post("/editor/api/validate?type=dataset_description", json=data)
    capsys.readouterr()  # the schema-loading chatter of Studio's own start-up
    code = 0
    try:
        cmd_json_editor_validate(SimpleNamespace(file=str(source), type="dataset_description", json=True))
    except SystemExit as exc:
        code = exc.code

    studio, cli = response.get_json(), json.loads(capsys.readouterr().out)
    assert code == (0 if studio["valid"] else 1)
    assert response.status_code == 200 and studio["success"]
    assert (cli["valid"], cli["errors"]) == (studio["valid"], studio["errors"])
    assert studio["valid"] == (not studio["errors"])
    assert studio["errors"] or data["Name"] == "x"  # the wrong-typed Name is really reported


def test_detecting_columns_answers_the_same_in_the_cli_and_in_studio(tmp_path, capsys):
    import io

    from flask import Flask

    from src.cli.commands.survey import cmd_survey_detect_columns
    from src.web.blueprints.tools_generation_handlers import handle_detect_columns

    table = b"Code;visit;trial;q1\nA1;pre;1;3\nA2;post;2;4\nA3;pre;1;5\n"
    source = tmp_path / "data.csv"
    source.write_bytes(table)

    with Flask(__name__).test_request_context(
        method="POST",
        data={"separator": "semicolon", "run_column_override": "trial", "file": (io.BytesIO(table), "data.csv")},
        content_type="multipart/form-data",
    ):
        studio = handle_detect_columns().get_json()
    cmd_survey_detect_columns(SimpleNamespace(
        file=str(source), separator="semicolon", session_column="", run_column="trial", json=True,
    ))

    cli = json.loads(capsys.readouterr().out)
    assert cli == studio
    assert studio["columns"] == ["Code", "visit", "trial", "q1"]
    assert studio["detected_sessions"] == ["post", "pre"] and studio["detected_runs"] == ["1", "2"]


def test_peeking_into_a_wide_table_answers_the_same_in_the_cli_and_in_studio(tmp_path, capsys):
    import io

    from flask import Flask

    from src.cli.commands.file_management import cmd_file_management_raw_peek
    from src.web.blueprints.tools import api_file_management_raw_peek

    table = b"participant_id,age,sex\nsub-001,25,F\nsub-002,22,X\n"
    source = tmp_path / "wide.csv"
    source.write_bytes(table)

    with Flask(__name__).test_request_context(
        method="POST", data={"data": (io.BytesIO(table), "wide.csv")}, content_type="multipart/form-data"
    ):
        studio = api_file_management_raw_peek().get_json()
    cmd_file_management_raw_peek(SimpleNamespace(input=str(source), sheet="", json=True))

    cli = json.loads(capsys.readouterr().out)
    assert cli == studio
    assert studio["total_rows"] == 2 and studio["columns"] == ["participant_id", "age", "sex"]
