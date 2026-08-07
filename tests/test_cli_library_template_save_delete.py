"""Tests for `prism_tools.py library template-save` / `template-delete`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2) found that no CLI
command could create/edit/remove a single project-library template JSON —
only the Studio GUI's Template Editor Save/Delete actions could. The
validation pipeline these commands use (strip_template_editor_internal_keys,
normalize_survey_template_for_validation, validate_template_against_schema)
was extracted from the same blueprint files in this and an earlier commit
so both entry points share it exactly.
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

from src.cli.commands.library import (  # noqa: E402
    cmd_library_template_delete,
    cmd_library_template_save,
)

GAD7_PATH = (
    Path(__file__).resolve().parent.parent
    / "official"
    / "library"
    / "survey"
    / "survey-gad7.json"
)


def _save_args(**overrides) -> SimpleNamespace:
    defaults = dict(
        project=None,
        modality="survey",
        filename=None,
        template=None,
        schema_version="stable",
        is_global=False,
        force=False,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _delete_args(**overrides) -> SimpleNamespace:
    defaults = dict(project=None, modality="survey", filename=None, yes=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.skipif(not GAD7_PATH.exists(), reason="Global library not available")
class TestTemplateSave:
    def test_saves_valid_template_into_project_library(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()

        cmd_library_template_save(
            _save_args(
                project=str(project),
                filename="survey-gad7.json",
                template=str(GAD7_PATH),
                is_global=True,
            )
        )

        saved = project / "code" / "library" / "survey" / "survey-gad7.json"
        assert saved.exists()
        assert "Saved to" in capsys.readouterr().out

    def test_appends_json_extension_if_missing(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()

        cmd_library_template_save(
            _save_args(
                project=str(project),
                filename="survey-gad7",
                template=str(GAD7_PATH),
                is_global=True,
            )
        )

        assert (
            project / "code" / "library" / "survey" / "survey-gad7.json"
        ).exists()

    def test_refuses_to_overwrite_without_force(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()

        cmd_library_template_save(
            _save_args(
                project=str(project),
                filename="survey-gad7.json",
                template=str(GAD7_PATH),
                is_global=True,
            )
        )

        with pytest.raises(SystemExit) as exc_info:
            cmd_library_template_save(
                _save_args(
                    project=str(project),
                    filename="survey-gad7.json",
                    template=str(GAD7_PATH),
                    is_global=True,
                )
            )
        assert exc_info.value.code == 1
        assert "already exists" in capsys.readouterr().out

    def test_force_overwrites_existing(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        target = project / "code" / "library" / "survey" / "survey-gad7.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}", encoding="utf-8")

        cmd_library_template_save(
            _save_args(
                project=str(project),
                filename="survey-gad7.json",
                template=str(GAD7_PATH),
                force=True,
                is_global=True,
            )
        )

        saved = json.loads(target.read_text(encoding="utf-8"))
        assert "Study" in saved

    def test_rejects_path_separators_in_filename(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            cmd_library_template_save(
                _save_args(
                    project=str(project),
                    filename="../escape.json",
                    template=str(GAD7_PATH),
                )
            )
        assert exc_info.value.code == 1
        assert "bare filename" in capsys.readouterr().out

    def test_missing_template_file_exits(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            cmd_library_template_save(
                _save_args(
                    project=str(project),
                    filename="x.json",
                    template=str(tmp_path / "missing.json"),
                )
            )
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().out

    def test_invalid_template_fails_schema_validation(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        bad_template = tmp_path / "bad.json"
        bad_template.write_text(json.dumps({"not": "a valid template"}), encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_library_template_save(
                _save_args(
                    project=str(project), filename="bad.json", template=str(bad_template)
                )
            )
        assert exc_info.value.code == 1
        assert "validation failed" in capsys.readouterr().out

    def test_non_object_template_exits(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        bad_template = tmp_path / "bad.json"
        bad_template.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_library_template_save(
                _save_args(
                    project=str(project), filename="bad.json", template=str(bad_template)
                )
            )
        assert exc_info.value.code == 1
        assert "JSON object" in capsys.readouterr().out


@pytest.mark.skipif(not GAD7_PATH.exists(), reason="Global library not available")
class TestTemplateDelete:
    def test_deletes_with_yes_flag(self, tmp_path, capsys):
        project = tmp_path / "project"
        target = project / "code" / "library" / "survey" / "survey-gad7.json"
        target.parent.mkdir(parents=True)
        target.write_text(GAD7_PATH.read_text(encoding="utf-8"), encoding="utf-8")

        cmd_library_template_delete(
            _delete_args(
                project=str(project), filename="survey-gad7.json", yes=True
            )
        )

        assert not target.exists()
        assert "Deleted" in capsys.readouterr().out

    def test_declining_confirmation_keeps_file(self, tmp_path, monkeypatch):
        project = tmp_path / "project"
        target = project / "code" / "library" / "survey" / "survey-gad7.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}", encoding="utf-8")

        monkeypatch.setattr("builtins.input", lambda prompt: "n")
        cmd_library_template_delete(
            _delete_args(project=str(project), filename="survey-gad7.json")
        )

        assert target.exists()

    def test_missing_file_exits(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            cmd_library_template_delete(
                _delete_args(
                    project=str(project), filename="does-not-exist.json", yes=True
                )
            )
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().out

    def test_rejects_path_traversal_outside_project_library(self, tmp_path, capsys):
        project = tmp_path / "project"
        project.mkdir()
        # Attempt to delete something outside the project's own library dir.
        outside_target = tmp_path / "outside.json"
        outside_target.write_text("{}", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_library_template_delete(
                _delete_args(
                    project=str(project),
                    filename="../../../outside.json",
                    yes=True,
                )
            )
        assert exc_info.value.code == 1
        assert outside_target.exists()
