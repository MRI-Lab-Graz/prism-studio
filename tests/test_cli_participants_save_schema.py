"""Tests for `prism_tools.py participants save-schema`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2) found that the Studio
GUI's Neurobagel widget "Save Annotations" button (POST
/api/projects/participants -> handle_save_participants_schema) had no CLI
equivalent, and its schema-canonicalization logic lived only as private
functions in projects_participants_handlers.py. That logic was extracted
into src.participants_backend (canonicalize_participants_schema_keys,
merge_participants_schema_field, is_participant_id_field) in the same
change, so both the GUI route and this CLI command share it.
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

from src.cli.commands.participants import cmd_participants_save_schema  # noqa: E402


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(
        project=None, schema_json=None, survey_selected_schema=None, json=False
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestSaveFromSchemaJson:
    def test_saves_and_adds_participant_id_default(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        schema_path = tmp_path / "schema.json"
        schema_path.write_text(
            json.dumps({"sex": {"Description": "Biological sex"}}), encoding="utf-8"
        )

        cmd_participants_save_schema(
            _args(project=str(project), schema_json=str(schema_path))
        )

        saved = json.loads((project / "participants.json").read_text(encoding="utf-8"))
        assert "participant_id" in saved
        assert saved["participant_id"]["Description"] == "Unique participant identifier"
        assert "sex" in saved
        assert "Saved" in capsys.readouterr().out

    def test_canonicalizes_neurobagel_annotated_id_field(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        schema_path = tmp_path / "schema.json"
        schema_path.write_text(
            json.dumps(
                {
                    "Code": {
                        "Annotations": {
                            "IsAbout": {"TermURL": "nb:ParticipantID", "Label": "ID"}
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        cmd_participants_save_schema(
            _args(project=str(project), schema_json=str(schema_path))
        )

        saved = json.loads((project / "participants.json").read_text(encoding="utf-8"))
        assert "Code" not in saved
        assert "participant_id" in saved
        assert saved["participant_id"]["Annotations"]["IsAbout"]["TermURL"] == (
            "nb:ParticipantID"
        )

    def test_json_mode_reports_fields(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        schema_path = tmp_path / "schema.json"
        schema_path.write_text(
            json.dumps({"age": {"Description": "Age"}}), encoding="utf-8"
        )

        cmd_participants_save_schema(
            _args(project=str(project), schema_json=str(schema_path), json=True)
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert "age" in payload["fields"]

    def test_missing_project_exits(self, tmp_path, capsys):
        schema_path = tmp_path / "schema.json"
        schema_path.write_text("{}", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_participants_save_schema(
                _args(
                    project=str(tmp_path / "missing"), schema_json=str(schema_path)
                )
            )
        assert exc_info.value.code == 1
        assert "not a directory" in capsys.readouterr().out

    def test_missing_schema_file_exits(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            cmd_participants_save_schema(
                _args(project=str(project), schema_json=str(tmp_path / "missing.json"))
            )
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().out

    def test_neither_flag_provided_exits(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            cmd_participants_save_schema(_args(project=str(project)))
        assert exc_info.value.code == 1
        assert "required" in capsys.readouterr().out


class TestSaveFromSurveySelectedSchema:
    def test_merges_into_existing_participants_json(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / "participants.json").write_text(
            json.dumps(
                {"participant_id": {"Description": "Unique participant identifier"}}
            ),
            encoding="utf-8",
        )
        selected_path = tmp_path / "selected.json"
        selected_path.write_text(
            json.dumps({"ADS01": {"Description": "Item 1"}}), encoding="utf-8"
        )

        cmd_participants_save_schema(
            _args(project=str(project), survey_selected_schema=str(selected_path))
        )

        saved = json.loads((project / "participants.json").read_text(encoding="utf-8"))
        assert "ADS01" in saved
        assert "participant_id" in saved

    def test_missing_survey_selected_file_exits(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            cmd_participants_save_schema(
                _args(
                    project=str(project),
                    survey_selected_schema=str(tmp_path / "missing.json"),
                )
            )
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().out
