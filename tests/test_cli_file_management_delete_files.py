"""Tests for `prism_tools.py file-management delete-files` /
`prism.py file-management delete-files`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2) found that the Studio
GUI's File Management -> Delete Files action (src.bids_file_deleter.
BidsFileDeleter) had no CLI equivalent — despite BidsFileDeleter already
generating a "python prism.py file-management delete-files ..." backend
command string for display, that command never actually existed. This
implements it and wires `prism.py file-management` to delegate into the
prism_tools CLI tree, mirroring the existing `wide-to-long` alias.
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

from src.cli.commands.file_management import (  # noqa: E402
    cmd_file_management_delete_files,
)


def _touch(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(
        project=None,
        modality=None,
        entity_filter=None,
        subjects=None,
        apply=False,
        yes=False,
        json=False,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestPreview:
    def test_preview_lists_matched_files_without_deleting(self, tmp_path, capsys):
        project_root = tmp_path / "project"
        target = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
        _touch(target)

        cmd_file_management_delete_files(
            _args(project=str(project_root), modality="func")
        )

        out = capsys.readouterr().out
        assert "1 file(s) matched" in out
        assert "Preview only" in out
        assert target.exists()

    def test_json_preview(self, tmp_path, capsys):
        project_root = tmp_path / "project"
        target = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
        _touch(target)

        cmd_file_management_delete_files(
            _args(project=str(project_root), modality="func", json=True)
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["applied"] is False
        assert payload["file_count"] == 1
        assert target.exists()


class TestApply:
    def test_apply_deletes_matched_files(self, tmp_path, capsys):
        project_root = tmp_path / "project"
        target = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
        _touch(target)

        cmd_file_management_delete_files(
            _args(project=str(project_root), modality="func", apply=True, yes=True)
        )

        out = capsys.readouterr().out
        assert "Done" in out
        assert not target.exists()

    def test_apply_json_reports_result(self, tmp_path, capsys):
        project_root = tmp_path / "project"
        target = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
        _touch(target)

        cmd_file_management_delete_files(
            _args(
                project=str(project_root),
                modality="func",
                apply=True,
                yes=True,
                json=True,
            )
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["applied"] is True
        assert payload["deleted_count"] == 1
        assert not target.exists()

    def test_entity_filter_restricts_matches(self, tmp_path, capsys):
        project_root = tmp_path / "project"
        keep = project_root / "sub-001" / "func" / "sub-001_task-other_bold.nii.gz"
        remove = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
        _touch(keep)
        _touch(remove)

        cmd_file_management_delete_files(
            _args(
                project=str(project_root),
                modality="func",
                entity_filter=["task=rest"],
                apply=True,
                yes=True,
            )
        )

        assert keep.exists()
        assert not remove.exists()

    def test_subjects_filter_restricts_matches(self, tmp_path, capsys):
        project_root = tmp_path / "project"
        keep = project_root / "sub-002" / "func" / "sub-002_task-rest_bold.nii.gz"
        remove = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
        _touch(keep)
        _touch(remove)

        cmd_file_management_delete_files(
            _args(
                project=str(project_root),
                modality="func",
                subjects="001",
                apply=True,
                yes=True,
            )
        )

        assert keep.exists()
        assert not remove.exists()

    def test_no_matches_reports_and_applies_nothing(self, tmp_path, capsys):
        project_root = tmp_path / "project"
        keep = project_root / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
        _touch(keep)

        cmd_file_management_delete_files(
            _args(
                project=str(project_root),
                modality="func",
                entity_filter=["task=doesnotexist"],
                apply=True,
                yes=True,
            )
        )

        out = capsys.readouterr().out
        assert "No files match" in out
        assert keep.exists()


class TestEntityFilterParsing:
    def test_malformed_entity_filter_exits(self, tmp_path, capsys):
        project_root = tmp_path / "project"
        project_root.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            cmd_file_management_delete_files(
                _args(project=str(project_root), entity_filter=["not-a-kv-pair"])
            )
        assert exc_info.value.code == 1
        assert "must be key=value" in capsys.readouterr().out


class TestNoFiltersRaises:
    def test_requires_at_least_one_filter(self, tmp_path, capsys):
        project_root = tmp_path / "project"
        project_root.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            cmd_file_management_delete_files(_args(project=str(project_root)))
        assert exc_info.value.code == 1
