"""A code map links self-chosen codes to participant numbers: no export or share may carry one."""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.code_maps import is_code_map  # noqa: E402

MAPS = [
    "code/old/survey_code_map.tsv",
    "code/survey_code_map - Kopie.xlsx",
    "code/survey_code_map.tsv",
    "code/survey_task-ads_ses-3_code_map.tsv",
]
MESSAGE = "Left out of the export (they re-identify participants): " + ", ".join(MAPS)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "study"
    for rel in [*MAPS, "code/keep.txt", "sub-001/ses-1/survey/sub-001_ses-1_task-ads_survey.tsv"]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("code\tparticipant_id\nAAAA\tsub-001\n", encoding="utf-8")
    (root / "project.json").write_text(json.dumps({"Basics": {"Name": "N"}}), encoding="utf-8")
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "N", "BIDSVersion": "1.9.0"}), encoding="utf-8"
    )
    return root


def _check(exported: set[str]):
    assert not [name for name in exported if "code_map" in name.lower()]
    assert any(name.endswith("code/keep.txt") for name in exported)


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_is_code_map():
    assert all(is_code_map(tuple(m.split("/"))) for m in MAPS)
    assert not is_code_map(("code", "recipes", "recipe-ads.json"))
    assert not is_code_map(("sourcedata", "survey_code_map.tsv"))


def test_zip_export_leaves_code_maps_out(project, tmp_path, capsys):
    from src.project_export import export_project

    target = tmp_path / "share.zip"
    stats = export_project(project, target, anonymize=False, mask_questions=False, include_code=True)
    with zipfile.ZipFile(target) as archive:
        _check(set(archive.namelist()))
    assert stats["code_maps_left_out"] == MAPS
    assert MESSAGE in capsys.readouterr().out


def test_folder_export_leaves_code_maps_out(project, tmp_path):
    from src.project_manager import ProjectManager

    result = ProjectManager().export_project_to_plain_folder(project, output_root=tmp_path / "out")
    assert result["success"], result
    _check(_files(Path(result["output_path"])))
    assert result["code_maps_left_out"] == MAPS


def test_folder_export_command_says_what_it_left_out(capsys):
    from src.cli.commands.export import _print_left_out

    _print_left_out({"code_maps_left_out": MAPS})
    assert MESSAGE in capsys.readouterr().out
    _print_left_out({})
    assert capsys.readouterr().out == ""


def test_anc_export_leaves_code_maps_out(project):
    from src.export_options import run_anc_export

    result = run_anc_export(project, {})
    _check(_files(Path(result["output_path"])))
    assert result["code_maps_left_out"] == MAPS


def test_template_export_leaves_code_maps_out(project, tmp_path):
    from src.project_template_export import export_project_template_zip

    target = tmp_path / "template.zip"
    stats = export_project_template_zip(project, target)
    with zipfile.ZipFile(target) as archive:
        _check(set(archive.namelist()))
    assert stats["code_maps_left_out"] == MAPS


def test_git_never_takes_a_code_map(project):
    from src.git_exclude import SENSITIVE_PATHS, ensure_git_excluded

    subprocess.run(["git", "init", "-q", str(project)], check=True)
    ensure_git_excluded(project, *SENSITIVE_PATHS)
    ignored = subprocess.run(
        ["git", "-C", str(project), "check-ignore", *MAPS], capture_output=True, text=True
    ).stdout.splitlines()
    assert sorted(ignored) == MAPS
