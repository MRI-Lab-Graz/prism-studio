"""`prism_tools.py export project` is Studio's export: the same options, the same gate, the same zip (THE RULE, CLAUDE.md)."""

import argparse
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src import export_options as eo  # noqa: E402
from src.cli.commands.export import cmd_export_project, export_data_from_args  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "app"


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "study"
    (project / "sub-001").mkdir(parents=True)
    (project / "dataset_description.json").write_text('{"Name": "N"}', encoding="utf-8")
    (project / "participants.tsv").write_text("participant_id\nsub-001\n", encoding="utf-8")
    (project / "sub-001" / "sub-001_task-x_survey.tsv").write_text("v\n1\n", encoding="utf-8")
    return project


def _args(project, **overrides):
    args = dict(
        project=str(project), output_folder=None, no_anonymize=False, no_mask_questions=False, preset="standard",
        include_sourcedata=False, no_derivatives=False, no_code=False, include_analysis=False, exclude_subject=None,
        exclude_session=None, exclude_modality=None, exclude_acq=None, exclude_task=None, scrub_mri_json=False,
        scrub_group=None, phenotype_bridge=False, repository_mode=None, validation_mode="ignore",
    )
    args.update(overrides)
    return SimpleNamespace(**args)


def test_the_command_writes_the_zip_next_to_the_project_like_studios_default(tmp_path, capsys):
    project = _project(tmp_path)
    cmd_export_project(_args(project, no_anonymize=True))
    zip_path = tmp_path / eo.export_zip_name("study", False, "standard")
    assert zip_path.exists() and "dataset_description.json" in zipfile.ZipFile(zip_path).namelist()
    assert str(zip_path) in capsys.readouterr().out


def test_the_options_the_flags_build_are_the_options_studios_page_sends(tmp_path):
    data = export_data_from_args(_args(
        _project(tmp_path), no_anonymize=True, preset="upload_ready", exclude_subject=["sub-01"], exclude_acq=["anat=a", "anat=b"],
        exclude_task=["func=rest"], repository_mode="datalad_preserving", scrub_group=["A"], scrub_mri_json=True,
    ))
    assert data == {
        "anonymize": False, "mask_questions": True, "export_preset": "upload_ready", "include_derivatives": True,
        "include_sourcedata": False, "include_code": True, "include_analysis": False, "exclude_subjects": ["sub-01"],
        "exclude_sessions": [], "exclude_modalities": [], "exclude_acq": {"anat": ["a", "b"]}, "exclude_tasks": {"func": ["rest"]},
        "scrub_mri_json": True, "scrub_mri_json_groups": ["A"], "export_phenotype_bridge": False,
        "repository_mode": "datalad_preserving", "validation_mode": "ignore",
        "output_folder": None, "materialize_annex_content": False, "init_git_lfs_repo": True,
    }


def test_every_option_studio_understands_has_a_flag():
    from src.cli.parser import build_prism_tools_parsers

    _root, parsers = build_prism_tools_parsers(APP)
    sub = [a for a in parsers["export"]._actions if isinstance(a, argparse._SubParsersAction)][0]
    flags = {a.dest for a in sub.choices["project"]._actions}
    needed = {"project", "output_folder", "preset", "include_sourcedata", "include_analysis", "scrub_mri_json", "phenotype_bridge",
              "repository_mode", "validation_mode", "exclude_subject", "exclude_session", "exclude_modality", "exclude_acq", "exclude_task"}
    assert needed <= flags, sorted(needed - flags)


def test_a_failing_validation_blocks_the_export_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    project = _project(tmp_path)
    monkeypatch.setattr(eo, "run_pre_export_validation", lambda *a: "Export blocked: 1 error")
    with pytest.raises(SystemExit) as exit_info:
        cmd_export_project(_args(project, validation_mode="both"))
    assert exit_info.value.code == 1 and "Export blocked" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.zip"))


def test_the_command_warns_about_scans_that_are_not_defaced_like_studios_export_status(tmp_path, capsys, monkeypatch):
    from unittest.mock import patch

    project = _project(tmp_path)
    report = [{"status": "not_defaced"}, {"status": "defaced"}, {"status": "unknown"}]
    with patch("src.mri_json_scrubber.build_defacing_report", lambda *a, **k: report):
        cmd_export_project(_args(project, no_anonymize=True))
    out = capsys.readouterr().out
    assert "includes 2 anatomical scans that are not defaced" in out and "Exported to" in out  # a warning, not a block
