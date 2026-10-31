"""Physio batch convert has four ways in: the command, Studio's synchronous route with a folder, the same route with
uploaded files, and the asynchronous job. They run one workflow (THE RULE, CLAUDE.md): they must hand the same
arguments to the save-to-project step, refuse the same conflicts and report the same warnings."""

import importlib
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from flask import Flask  # noqa: E402

from src.batch_convert import FileConflict  # noqa: E402
from src.cli.commands.convert import cmd_physio_batch_convert  # noqa: E402
from tests.test_physio_batch_saves_into_the_project import READY_PROJECT, _cli_args, fake_batch_convert_folder  # noqa: E402

SAVE_KEYS = ("dataset_name", "dest_root", "flat_structure", "modality_filter", "subject_rewrite_mode")
FORM = {"modality": "all", "save_to_project": "true", "dataset_name": "Converted Dataset", "dest_root": "rawdata"}
HANDLERS = "src.web.blueprints.conversion_physio_handlers"
DEFAULT_MESSAGE = "<default>"  # the save step's own commit message: nobody overrides it


@pytest.fixture
def world(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "sub-144001_ses-1_physio.raw").write_text("x", encoding="utf-8")
    saves = []

    def fake_save(**kwargs):
        saves.append(kwargs)
        return SimpleNamespace(output_paths=[], datalad=None, warnings=["a new subject folder was created"])

    handlers = importlib.import_module(HANDLERS)
    monkeypatch.setattr("src.batch_convert.batch_convert_folder", fake_batch_convert_folder)
    monkeypatch.setattr(handlers, "batch_convert_folder", fake_batch_convert_folder)
    monkeypatch.setattr("src.conversion_to_project.save_physio_batch_to_project", fake_save)
    monkeypatch.setattr(handlers, "save_physio_batch_to_project", fake_save)
    # the asynchronous job runs inline, so the test can read its result
    monkeypatch.setattr(handlers.threading, "Thread", lambda target, args, daemon: SimpleNamespace(start=lambda: target(*args)))
    return project, raw, saves


def _client(project):
    handlers = importlib.import_module(HANDLERS)
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.add_url_rule("/sync", view_func=handlers.api_batch_convert, methods=["POST"])
    app.add_url_rule("/start", view_func=handlers.api_batch_convert_start, methods=["POST"])
    app.add_url_rule("/status/<job_id>", view_func=handlers.api_batch_convert_status)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["current_project_path"] = str(project)
    return client


def _cli(project, raw, capsys):
    try:
        cmd_physio_batch_convert(_cli_args(raw, project, dest_root="rawdata"))
    except SystemExit:
        pass
    captured = capsys.readouterr()
    return captured.out + captured.err


def _sync_folder(project, raw, capsys):
    return _client(project).post("/sync", data={**FORM, "folder_path": str(raw)}).get_data(as_text=True)


def _sync_upload(project, raw, capsys):
    upload = (io.BytesIO(b"x"), "sub-144001_ses-1_physio.raw")
    response = _client(project).post("/sync", data={**FORM, "files[]": upload}, content_type="multipart/form-data")
    return response.get_data(as_text=True)


def _async_job(project, raw, capsys):
    client = _client(project)
    started = client.post("/start", data={**FORM, "folder_path": str(raw)})
    if started.status_code != 200:
        return started.get_data(as_text=True)
    return client.get(f"/status/{started.get_json()['job_id']}").get_data(as_text=True)


ENTRYPOINTS = {"cli": _cli, "sync folder": _sync_folder, "sync upload": _sync_upload, "async job": _async_job}


def test_every_entrypoint_hands_the_same_arguments_to_the_save_to_project_step(world, capsys):
    project, raw, saves = world
    seen = {}
    for name, run in ENTRYPOINTS.items():
        saves.clear()
        run(project, raw, capsys)
        assert len(saves) == 1, f"{name} did not save into the project"
        seen[name] = {key: saves[0].get(key) for key in SAVE_KEYS} | {"run_message": saves[0].get("run_message", DEFAULT_MESSAGE)}
    assert len({tuple(sorted(v.items())) for v in seen.values()}) == 1, seen


def test_every_entrypoint_refuses_conflicting_files_before_saving(world, monkeypatch, capsys):
    project, raw, saves = world

    def with_conflict(source_folder, output_folder, **kwargs):
        result = fake_batch_convert_folder(source_folder, output_folder, **kwargs)
        result.conflicts = [FileConflict(output_path=Path(output_folder) / "sub-144001" / "x.tsv", reason="different")]
        return result

    handlers = importlib.import_module(HANDLERS)
    monkeypatch.setattr("src.batch_convert.batch_convert_folder", with_conflict)
    monkeypatch.setattr(handlers, "batch_convert_folder", with_conflict)
    for name, run in ENTRYPOINTS.items():
        saves.clear()
        said = run(project, raw, capsys)
        assert not saves, f"{name} saved files that conflict"
        assert "File conflicts detected: 1 files" in said, (name, said[:300])


def test_every_entrypoint_reports_the_warnings_of_the_save_step(world, capsys):
    project, raw, _saves = world
    for name, run in ENTRYPOINTS.items():
        said = run(project, raw, capsys)
        assert "a new subject folder was created" in said, (name, said[:300])


def _batch_parser():
    import argparse

    from src.cli.parser import build_prism_tools_parsers

    _root, parsers = build_prism_tools_parsers(Path(__file__).resolve().parents[1] / "app")
    sub = [a for a in parsers["physio"]._actions if isinstance(a, argparse._SubParsersAction)][0]
    return sub.choices["batch-convert"]


def test_studio_and_the_command_convert_with_the_same_defaults(world, monkeypatch):
    """Only the folder and the project given: both hand the converter and the save step the same arguments."""
    project, raw, saves = world
    handlers = importlib.import_module(HANDLERS)
    converter_calls = []

    def recording_converter(source_folder, output_folder, **kwargs):
        converter_calls.append(kwargs)
        return fake_batch_convert_folder(source_folder, output_folder, **kwargs)

    monkeypatch.setattr("src.batch_convert.batch_convert_folder", recording_converter)
    monkeypatch.setattr(handlers, "batch_convert_folder", recording_converter)

    cmd_physio_batch_convert(_batch_parser().parse_args(["--input", str(raw), "--project", str(project)]))
    _client(project).post("/sync", data={"folder_path": str(raw), "save_to_project": "true"})

    (cli_call, studio_call), (cli_save, studio_save) = converter_calls, saves
    for key in ("physio_sampling_rate", "generate_physio_reports", "modality_filter", "dry_run", "physio_destination"):
        assert cli_call[key] == studio_call[key], (key, cli_call[key], studio_call[key])
    for key in SAVE_KEYS:
        assert cli_save[key] == studio_save[key], (key, cli_save[key], studio_save[key])
