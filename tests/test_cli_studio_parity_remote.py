"""Studio only triggers what the CLI runs: project config and remote-target routes (see test_cli_studio_parity.py)."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_cli_studio_parity import _two_projects

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


def _prismrc(root: Path) -> dict:
    return json.loads((root / ".prismrc.json").read_text(encoding="utf-8"))


def _studio_in_app(handler, body, **kwargs):
    from flask import Flask

    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    with app.test_request_context(method="POST", json=body):
        response = handler(**kwargs)
    response, status = (response, 200) if not isinstance(response, tuple) else response
    return response.get_json(), status


def test_setting_the_schema_version_writes_the_same_config_in_the_cli_and_in_studio(tmp_path, capsys):
    from src.cli.commands.project import cmd_project_set_schema_version
    from src.web.blueprints.projects_schema_config_handlers import handle_save_project_schema_config

    cli, studio = _two_projects(tmp_path)
    cmd_project_set_schema_version(SimpleNamespace(project=str(cli), version="stable"))
    body, status = _studio_in_app(
        handle_save_project_schema_config, {"project_path": str(studio), "schema_version": "stable"}, get_current_project=lambda: {}
    )
    assert status == 200 and body["success"]
    assert _prismrc(cli) == _prismrc(studio)

    with pytest.raises(SystemExit):  # an unknown version is refused by both, with the same words
        cmd_project_set_schema_version(SimpleNamespace(project=str(cli), version="v9.9"))
    body, status = _studio_in_app(
        handle_save_project_schema_config, {"project_path": str(studio), "schema_version": "v9.9"}, get_current_project=lambda: {}
    )
    assert status == 400 and body["error"] in capsys.readouterr().out


def test_saving_the_datalad_server_config_writes_the_same_file_in_the_cli_and_in_studio(tmp_path, capsys):
    from src.cli.commands.datalad import cmd_datalad_config
    from src.web.blueprints.projects_datalad_server_blueprint import datalad_server_save_config

    cli, studio = _two_projects(tmp_path)
    cmd_datalad_config(SimpleNamespace(project=str(cli), url="ssh://host/store", sibling_name="lab", alias="study"))
    body, status = _studio_in_app(
        datalad_server_save_config,
        {"project_path": str(studio), "ria_url": "ssh://host/store", "sibling_name": "lab", "alias": "study"},
    )
    assert status == 200 and body["success"]
    assert _prismrc(cli) == _prismrc(studio)

    with pytest.raises(SystemExit):  # a bad label is refused by both, with the same words
        cmd_datalad_config(SimpleNamespace(project=str(cli), url=None, sibling_name="bad name!", alias=None))
    body, status = _studio_in_app(datalad_server_save_config, {"project_path": str(studio), "sibling_name": "bad name!"})
    assert status == 400 and body["error"] in capsys.readouterr().out


def test_saving_the_rsync_config_writes_the_same_file_in_the_cli_and_in_studio(tmp_path):
    from src.cli.commands.rsync import cmd_rsync_config
    from src.web.blueprints.projects_rsync_server_blueprint import rsync_server_save_config

    cli, studio = _two_projects(tmp_path)
    cmd_rsync_config(
        SimpleNamespace(project=str(cli), remote_target="host:/data", remote_label="Lab", exclude=["sourcedata/", " ", "sourcedata/", "*.tmp"])
    )
    body, status = _studio_in_app(
        rsync_server_save_config,
        {
            "project_path": str(studio),
            "remote_target": "host:/data",
            "remote_label": "Lab",
            "exclude_patterns": "sourcedata/\n \nsourcedata/\n*.tmp",
        },
    )
    assert status == 200 and body["success"]
    assert _prismrc(cli) == _prismrc(studio)
    assert body["exclude_patterns"] == ["sourcedata/", "*.tmp"]


def test_syncing_with_rsync_hands_the_manager_the_same_options_in_the_cli_and_in_studio(tmp_path, monkeypatch):
    import src.web.blueprints.projects_rsync_server_blueprint as blueprint
    from src.cli.commands.rsync import cmd_rsync_sync
    from src.project_manager import ProjectManager

    calls = []

    def fake_sync(self, project_path, **kwargs):
        calls.append({k: v for k, v in kwargs.items() if k not in ("progress_callback", "is_cancelled")})
        return {"success": True, "message": "Sync complete."}

    monkeypatch.setattr(ProjectManager, "sync_project_to_remote", fake_sync)

    class InlineThread:  # run the job where the test can see it
        def __init__(self, target, args, daemon):
            self.run = lambda: target(*args)

        def start(self):
            self.run()

    monkeypatch.setattr(blueprint.threading, "Thread", InlineThread)
    cli, studio = _two_projects(tmp_path)
    cmd_rsync_sync(
        SimpleNamespace(project=str(cli), remote_target="host:/data", remote_label=None, exclude=["*.tmp", "*.tmp"], verify=True, json=True)
    )
    body, status = _studio_in_app(
        blueprint.rsync_server_sync_start,
        {"project_path": str(studio), "remote_target": "host:/data", "exclude_patterns": ["*.tmp", "*.tmp"], "verify": True},
    )
    assert status == 200 and body["job_id"]
    assert len(calls) == 2 and calls[0] == calls[1]
