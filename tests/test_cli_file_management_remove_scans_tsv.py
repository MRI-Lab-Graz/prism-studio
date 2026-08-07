"""Tests for `prism_tools.py file-management remove-scans-tsv`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2) found that the Studio
GUI's File Management -> "Delete all scans.tsv" action
(ProjectManager.remove_scans_tsv_files, routed through
/api/projects/datalad/remove-scans-tsv) had no CLI equivalent.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.file_management import (  # noqa: E402
    cmd_file_management_remove_scans_tsv,
)
from src.project_manager import ProjectManager  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_project_manager import (  # noqa: E402
    _build_nested_project_with_scans_tsv,
)


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(project=None, yes=False, json=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestConfirmationRequirement:
    def test_declining_confirmation_does_not_call_manager(
        self, tmp_path, monkeypatch, capsys
    ):
        called = {}

        def _fake_remove(self, project_path):
            called["invoked"] = True
            return {"success": True, "removed": 0, "dataset_roots_touched": [], "errors": []}

        monkeypatch.setattr(ProjectManager, "remove_scans_tsv_files", _fake_remove)
        monkeypatch.setattr("builtins.input", lambda prompt: "n")

        cmd_file_management_remove_scans_tsv(_args(project=str(tmp_path)))

        assert "invoked" not in called
        assert "Aborted" in capsys.readouterr().out

    def test_json_mode_without_yes_exits_without_prompting(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cmd_file_management_remove_scans_tsv(
                _args(project=str(tmp_path), json=True)
            )
        assert exc_info.value.code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False

    def test_yes_flag_skips_prompt(self, tmp_path, monkeypatch):
        called = {}

        def _fake_remove(self, project_path):
            called["invoked"] = True
            return {"success": True, "removed": 0, "dataset_roots_touched": [], "errors": []}

        monkeypatch.setattr(ProjectManager, "remove_scans_tsv_files", _fake_remove)

        cmd_file_management_remove_scans_tsv(_args(project=str(tmp_path), yes=True))

        assert called.get("invoked") is True


class TestOutput:
    def test_reports_removed_count(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            ProjectManager,
            "remove_scans_tsv_files",
            lambda self, project_path: {
                "success": True,
                "removed": 3,
                "dataset_roots_touched": [tmp_path, tmp_path / "sub-001"],
                "errors": [],
            },
        )

        cmd_file_management_remove_scans_tsv(_args(project=str(tmp_path), yes=True))

        out = capsys.readouterr().out
        assert "3 scans.tsv file(s) removed" in out
        assert "2 dataset root(s)" in out

    def test_json_output_reports_full_result(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            ProjectManager,
            "remove_scans_tsv_files",
            lambda self, project_path: {
                "success": True,
                "removed": 1,
                "dataset_roots_touched": [str(tmp_path)],
                "errors": [],
            },
        )

        cmd_file_management_remove_scans_tsv(
            _args(project=str(tmp_path), yes=True, json=True)
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["removed"] == 1

    def test_manager_failure_exits_nonzero(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            ProjectManager,
            "remove_scans_tsv_files",
            lambda self, project_path: {
                "success": False,
                "removed": 0,
                "errors": ["git rm failed"],
                "message": "",
            },
        )

        with pytest.raises(SystemExit) as exc_info:
            cmd_file_management_remove_scans_tsv(_args(project=str(tmp_path), yes=True))
        assert exc_info.value.code == 1


class TestEndToEnd:
    def test_removes_scans_tsv_across_real_nested_project(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            project_path = _build_nested_project_with_scans_tsv(tmp)

            cmd_file_management_remove_scans_tsv(
                _args(project=str(project_path), yes=True)
            )

            out = capsys.readouterr().out
            assert "2 scans.tsv file(s) removed" in out
            assert not (project_path / "sub-001" / "sub-001_scans.tsv").exists()
            assert not (project_path / "sub-002" / "sub-002_scans.tsv").exists()
            assert (project_path / "sub-001" / "keep.txt").exists()
