"""`file-management rename-physio --apply --project` renames into a project like Studio's Physio Renamer (THE RULE, CLAUDE.md)."""

import importlib
import io
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from flask import Flask  # noqa: E402

from src.cli.commands.file_management import cmd_file_management_rename_physio  # noqa: E402

READY_PROJECT = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "single"},
}


@pytest.fixture
def world(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "rec1.edf").write_bytes(b"EDF one")
    return project, incoming


def _files(project: Path) -> dict[str, bytes]:
    return {p.relative_to(project).as_posix(): p.read_bytes() for p in sorted(project.rglob("*")) if p.is_file()}


def _cli_args(incoming, project, **overrides):
    args = dict(
        input=str(incoming), pattern=r"^rec1\.edf$", replacement="sub-1234_ses-1_physio.edf", id_source="filename",
        folder_subject_level=2, folder_session_level=1, folder_example_path="", folder_subject_value="",
        folder_session_value="", modality="physio", organize=True, apply=True, output=None, json=False,
        project=str(project), dest_root="root", flat_structure=False, subject_rewrite_mode="keep",
    )
    args.update(overrides)
    return SimpleNamespace(**args)


def _studio_rename(incoming, project, **form):
    handlers = importlib.import_module("src.web.blueprints.conversion_physio_handlers")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.add_url_rule("/api/physio-rename", view_func=handlers.api_physio_rename, methods=["POST"])
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(project)
        return client.post(
            "/api/physio-rename",
            data={
                "pattern": r"^rec1\.edf$", "replacement": "sub-1234_ses-1_physio.edf", "modality": "physio", "organize": "true",
                "save_to_project": "true", "skip_zip": "true",
                "files[]": (io.BytesIO((incoming / "rec1.edf").read_bytes()), "rec1.edf"), **form,
            },
            content_type="multipart/form-data",
        )


@pytest.mark.parametrize("options, form", [
    ({}, {}),
    ({"dest_root": "rawdata", "flat_structure": True}, {"dest_root": "rawdata", "flat_structure": "true"}),
    ({"subject_rewrite_mode": "last3"}, {"subject_rewrite_mode": "last3"}),
])
def test_the_command_and_studios_renamer_leave_the_same_project(world, tmp_path, options, form):
    project, incoming = world
    twin = tmp_path / "twin"
    shutil.copytree(project, twin)

    cmd_file_management_rename_physio(_cli_args(incoming, project, **options))
    response = _studio_rename(incoming, twin, **form)

    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    assert _files(project) == _files(twin)
    assert any(name.endswith("physio.edf") for name in _files(project)), _files(project)
    assert (incoming / "rec1.edf").exists()  # the original stays
