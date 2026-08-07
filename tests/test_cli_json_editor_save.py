"""Tests for `prism_tools.py json-editor save`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2) found that the Studio
GUI JSON Editor's "Save to Project" action — which writes
dataset_description.json/participants.json/samples.json/task-*.json
sidecars with real post-save validation via the bundled
backend.file_manager.FileManager / backend.json_validator.JSONValidator —
had no CLI equivalent, despite that backend being a genuinely isolated,
Flask-independent sub-app.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.json_editor import cmd_json_editor_save  # noqa: E402


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(project=None, type=None, file=None, json=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestJsonEditorSave:
    def test_saves_participants_json(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        source = tmp_path / "participants.json"
        source.write_text(
            json.dumps({"participant_id": {"Description": "A participant ID"}}),
            encoding="utf-8",
        )

        cmd_json_editor_save(
            _args(project=str(project), type="participants", file=str(source))
        )

        saved = project / "participants.json"
        assert saved.exists()
        assert json.loads(saved.read_text(encoding="utf-8")) == {
            "participant_id": {"Description": "A participant ID"}
        }
        assert "Saved to" in capsys.readouterr().out

    def test_saves_task_json(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        source = tmp_path / "task.json"
        source.write_text(json.dumps({"TaskName": "rest"}), encoding="utf-8")

        cmd_json_editor_save(
            _args(project=str(project), type="task-rest", file=str(source))
        )

        assert (project / "task-rest.json").exists()

    def test_json_mode_reports_result(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        source = tmp_path / "dataset_description.json"
        source.write_text(
            json.dumps({"Name": "Test Dataset", "BIDSVersion": "1.8.0"}),
            encoding="utf-8",
        )

        cmd_json_editor_save(
            _args(
                project=str(project),
                type="dataset_description",
                file=str(source),
                json=True,
            )
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["path"].endswith("dataset_description.json")

    def test_missing_project_directory_exits(self, tmp_path, capsys):
        source = tmp_path / "data.json"
        source.write_text("{}", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_json_editor_save(
                _args(
                    project=str(tmp_path / "missing"),
                    type="participants",
                    file=str(source),
                )
            )
        assert exc_info.value.code == 1
        assert "not a directory" in capsys.readouterr().out

    def test_missing_source_file_exits(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            cmd_json_editor_save(
                _args(
                    project=str(project),
                    type="participants",
                    file=str(tmp_path / "missing.json"),
                )
            )
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().out

    def test_invalid_json_source_exits(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        bad_source = tmp_path / "bad.json"
        bad_source.write_text("not json", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_json_editor_save(
                _args(project=str(project), type="participants", file=str(bad_source))
            )
        assert exc_info.value.code == 1
        assert "not valid JSON" in capsys.readouterr().out

    def test_unknown_json_type_exits(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        source = tmp_path / "data.json"
        source.write_text("{}", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_json_editor_save(
                _args(project=str(project), type="not-a-real-type", file=str(source))
            )
        assert exc_info.value.code == 1

    def test_overwrites_existing_file(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / "participants.json").write_text(
            json.dumps({"old": "data"}), encoding="utf-8"
        )
        source = tmp_path / "new.json"
        source.write_text(json.dumps({"participant_id": {}}), encoding="utf-8")

        cmd_json_editor_save(
            _args(project=str(project), type="participants", file=str(source))
        )

        saved = json.loads((project / "participants.json").read_text(encoding="utf-8"))
        assert saved == {"participant_id": {}}
