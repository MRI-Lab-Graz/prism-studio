"""The plain-folder export: one options function and one run, for `export folder` and Studio's route (THE RULE, CLAUDE.md)."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src import export_options as eo  # noqa: E402


def test_only_the_options_that_were_sent_are_passed_on():
    assert eo.build_folder_export_kwargs({}) == {"output_root": None}
    assert eo.build_folder_export_kwargs({"output_folder": "/x"}) == {"output_root": "/x"}


def test_mri_scrubbing_and_the_phenotype_bridge_are_passed_when_sent():
    kwargs = eo.build_folder_export_kwargs({"scrub_mri_json": True, "scrub_mri_json_groups": [" A "], "export_phenotype_bridge": True})
    assert kwargs["scrub_mri_json"] is True and kwargs["scrub_mri_json_groups"] == {"a"} and kwargs["export_phenotype_bridge"] is True
    assert "scrub_mri_json_groups" not in eo.build_folder_export_kwargs({"scrub_mri_json": False})


def test_any_scope_option_brings_the_folder_defaults_with_it():
    kwargs = eo.build_folder_export_kwargs({"exclude_subjects": ["sub-01"]})
    assert kwargs["exclude_subjects"] == {"sub-01"}
    assert (kwargs["include_derivatives"], kwargs["include_sourcedata"], kwargs["include_code"], kwargs["include_analysis"]) == (True, False, True, True)
    assert kwargs["materialize_annex_content"] is False and kwargs["exclude_sessions"] is None


def test_the_command_and_studios_route_hand_the_manager_the_same_arguments(tmp_path):
    import importlib

    from flask import Flask

    from src.cli.commands.export import cmd_export_folder, export_data_from_args

    project = tmp_path / "study"
    project.mkdir()
    args = SimpleNamespace(
        project=str(project), output_folder=str(tmp_path / "out"), no_anonymize=False, no_mask_questions=False, preset="standard",
        include_sourcedata=True, no_derivatives=False, no_code=False, include_analysis=False, exclude_subject=["sub-01"],
        exclude_session=None, exclude_modality=None, exclude_acq=["anat=a"], exclude_task=None, scrub_mri_json=True,
        scrub_group=["a"], phenotype_bridge=True, repository_mode=None, validation_mode="ignore", materialize_annex_content=False,
    )
    data = {**export_data_from_args(args), "project_path": str(project), "output_folder": str(tmp_path / "out"), "materialize_annex_content": False}
    seen = []

    def fake(self, project_root, **kwargs):
        seen.append(kwargs)
        return {"success": True}

    with patch("src.project_manager.ProjectManager.export_project_to_plain_folder", fake):
        cmd_export_folder(args)
        blueprint = importlib.import_module("src.web.blueprints.projects_export_blueprint")
        app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
        app.register_blueprint(blueprint.projects_export_bp)
        assert app.test_client().post("/api/projects/export/folder", json=data).status_code == 200
    assert len(seen) == 2 and seen[0] == seen[1], seen


def test_the_git_lfs_export_has_no_materialize_option_and_initializes_the_repo_by_default():
    assert eo.build_git_lfs_export_kwargs({}) == {"output_root": None, "init_git_lfs_repo": True}
    kwargs = eo.build_git_lfs_export_kwargs({"init_git_lfs_repo": False, "exclude_sessions": ["ses-2"], "materialize_annex_content": True})
    assert kwargs["init_git_lfs_repo"] is False and kwargs["exclude_sessions"] == {"ses-2"} and "materialize_annex_content" not in kwargs


def test_the_annex_availability_preview_always_carries_the_scope_defaults():
    kwargs = eo.build_annex_availability_kwargs({})
    assert (kwargs["include_derivatives"], kwargs["include_sourcedata"], kwargs["include_code"], kwargs["include_analysis"]) == (True, False, True, True)
    assert "exclude_subjects" not in kwargs
    assert eo.build_annex_availability_kwargs({"exclude_subjects": ["sub-1"]})["exclude_subjects"] == {"sub-1"}


@pytest.mark.parametrize("command, route, manager_method", [
    ("cmd_export_git_lfs", "/api/projects/export/git-lfs", "export_project_to_git_lfs_folder"),
    ("cmd_export_annex_availability", "/api/projects/export/annex-availability", "preview_plain_folder_export_availability"),
])
def test_the_command_and_studios_route_hand_the_manager_the_same_arguments_for_lfs_and_annex(tmp_path, command, route, manager_method):
    import importlib

    from flask import Flask

    import src.cli.commands.export as export_commands

    project = tmp_path / "study"
    project.mkdir()
    args = SimpleNamespace(
        project=str(project), output_folder=str(tmp_path / "out"), no_anonymize=False, no_mask_questions=False, preset="standard",
        include_sourcedata=True, no_derivatives=False, no_code=False, include_analysis=False, exclude_subject=["sub-01"],
        exclude_session=None, exclude_modality=None, exclude_acq=["anat=a"], exclude_task=None, scrub_mri_json=False,
        scrub_group=None, phenotype_bridge=False, repository_mode=None, validation_mode="ignore", materialize_annex_content=False,
        no_init_repo=False, json=False,
    )
    data = {**export_commands.export_data_from_args(args), "project_path": str(project), "init_git_lfs_repo": True}
    seen = []

    def fake(self, project_root, **kwargs):
        seen.append(kwargs)
        return {"success": True}

    with patch(f"src.project_manager.ProjectManager.{manager_method}", fake):
        getattr(export_commands, command)(args)
        blueprint = importlib.import_module("src.web.blueprints.projects_export_blueprint")
        app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
        app.register_blueprint(blueprint.projects_export_bp)
        assert app.test_client().post(route, json=data).status_code == 200
    assert len(seen) == 2 and seen[0] == seen[1], seen


def test_the_structure_command_lists_what_studios_export_page_offers(tmp_path, capsys):
    import json

    from src.cli.commands.export import cmd_export_structure

    project = tmp_path / "study"
    (project / "sub-01" / "ses-1" / "anat").mkdir(parents=True)
    cmd_export_structure(SimpleNamespace(project=str(project), json=True))
    structure = json.loads(capsys.readouterr().out)
    assert "sessions" in structure and "modalities" in structure
