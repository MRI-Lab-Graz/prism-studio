"""`biometrics convert` into a project behaves like Studio's Convert with "save to project" (THE RULE, CLAUDE.md)."""

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

from src.cli.commands.biometrics import cmd_biometrics_convert  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "official" / "library" / "biometrics" / "biometrics-fitness.json"
READY_PROJECT = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "single"},
}
pytestmark = pytest.mark.skipif(not FITNESS.exists(), reason="official library not available")


@pytest.fixture
def world(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    # participants already in the project, with padded IDs the table writes unpadded
    (project / "participants.tsv").write_text("participant_id\nsub-001\nsub-002\n", encoding="utf-8")
    table = tmp_path / "fitness.csv"
    table.write_text("participant_id,resting_hr\n1,60\n2,70\n", encoding="utf-8")
    return project, table


def _cli_args(project_dir, table, **overrides):
    args = dict(
        input=str(table), library_dir=None, output=str(project_dir), id_column=None, session_column=None, session="1",
        sheet="0", unknown="warn", tasks="", name=None, force=None, project=None, dry_run=False,
    )
    args.update(overrides)
    return SimpleNamespace(**args)


def _files(project: Path) -> dict[str, str]:
    return {
        p.relative_to(project).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(project.rglob("*")) if p.is_file() and ".git" not in p.parts
    }


def test_the_command_uses_the_project_ids_the_project_templates_and_leaves_what_studio_leaves(world, tmp_path):
    project, table = world
    twin = tmp_path / "twin"
    shutil.copytree(project, twin)

    cmd_biometrics_convert(_cli_args(project, table))

    handlers = importlib.import_module("src.web.blueprints.conversion_biometrics_handlers")
    app = Flask(__name__, root_path=str(ROOT / "app"))
    app.secret_key = os.urandom(32)
    app.add_url_rule("/api/biometrics-convert", view_func=handlers.api_biometrics_convert, methods=["POST"])
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(twin)
        response = client.post(
            "/api/biometrics-convert",
            data={"data": (io.BytesIO(table.read_bytes()), "fitness.csv"), "session": "1", "validate": "false", "save_to_project": "true"},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    assert list(project.glob("sub-001/ses-1/biometrics/*.tsv")), "the unpadded ID 1 was not matched to sub-001"
    # no project library: the template came from the official one and was copied into the project
    assert (project / "code" / "library" / "biometrics" / "biometrics-fitness.json").exists()
    assert _files(project) == _files(twin)


def test_a_dry_run_converts_but_writes_nothing_into_the_project(world, capsys):
    project, table = world
    cmd_biometrics_convert(_cli_args(project, table, dry_run=True))
    assert not list(project.glob("sub-*/**/*.tsv"))
    assert "dry" in capsys.readouterr().out.lower()
