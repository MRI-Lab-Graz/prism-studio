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
