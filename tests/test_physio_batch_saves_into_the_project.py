"""`physio batch-convert --project` saves like Studio's batch convert with "save to project" (THE RULE, CLAUDE.md)."""

import importlib
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from flask import Flask  # noqa: E402

from src.cli.commands.convert import cmd_physio_batch_convert  # noqa: E402

READY_PROJECT = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "single"},
}


def fake_batch_convert_folder(source_folder, output_folder, **kwargs):
    """Stands in for the real converter: one converted file, like a Varioport recording would give."""
    target = Path(output_folder) / "sub-144001" / "ses-1" / "physio"
    target.mkdir(parents=True, exist_ok=True)
    (target / "sub-144001_ses-1_task-rest_physio.tsv.gz").write_text("data", encoding="utf-8")
    converted = [SimpleNamespace(success=True, session="1", target_folder="physio", task="rest")]
    return SimpleNamespace(success_count=1, error_count=0, skipped=[], new_files=["x"], existing_files=[], converted=converted, conflicts=[])


@pytest.fixture
def world(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "recording.raw").write_text("x", encoding="utf-8")
    monkeypatch.setattr("src.batch_convert.batch_convert_folder", fake_batch_convert_folder)
    return project, raw


def _files(project: Path) -> dict[str, str]:
    return {p.relative_to(project).as_posix(): p.read_text(encoding="utf-8") for p in sorted(project.rglob("*")) if p.is_file()}


def _cli_args(raw, project, **overrides):
    args = dict(
        input=str(raw), output=None, modality="all", sampling_rate=None, dry_run=False, destination=None,
        generate_physio_reports=False, dataset_name="Converted Dataset", project=str(project),
        dest_root="root", flat_structure=False, subject_rewrite_mode="keep",
    )
    args.update(overrides)
    return SimpleNamespace(**args)


def _studio_batch(raw, project, **form):
    handlers = importlib.import_module("src.web.blueprints.conversion_physio_handlers")
    handlers.batch_convert_folder = fake_batch_convert_folder
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.add_url_rule("/api/batch-convert", view_func=handlers.api_batch_convert, methods=["POST"])
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(project)
        return client.post(
            "/api/batch-convert",
            data={"folder_path": str(raw), "modality": "all", "save_to_project": "true", "dataset_name": "Converted Dataset", **form},
        )


@pytest.mark.parametrize("options, form", [
    ({}, {}),
    ({"dest_root": "rawdata", "flat_structure": True}, {"dest_root": "rawdata", "flat_structure": "true"}),
    ({"subject_rewrite_mode": "last3"}, {"subject_rewrite_mode": "last3"}),
])
def test_the_command_and_studios_batch_route_leave_the_same_project(world, tmp_path, options, form):
    project, raw = world
    twin = tmp_path / "twin"
    shutil.copytree(project, twin)

    cmd_physio_batch_convert(_cli_args(raw, project, **options))
    response = _studio_batch(raw, twin, **form)

    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    assert _files(project) == _files(twin)
    assert any("physio" in name for name in _files(project)), _files(project)


def test_a_dry_run_with_a_project_writes_nothing_into_it(world):
    project, raw = world
    cmd_physio_batch_convert(_cli_args(raw, project, dry_run=True))
    assert not list(project.glob("sub-*"))
