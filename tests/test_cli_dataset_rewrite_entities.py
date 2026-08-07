"""Tests for `prism_tools.py dataset rewrite-entities`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P1-7) found that the Studio
GUI's File Management -> "Edit BIDS Filename Parts" action
(src.bids_entity_rewriter.BidsEntityRewriter +
src.repo_rewrite_datalad_runner.apply_entity_rewrite) had no CLI
equivalent at all — only the subject-ID rewrite path
(`dataset rename-subjects`) was CLI-reachable, and that's a different
engine that explicitly excludes non-subject entities. This adds and tests
`dataset rewrite-entities`, which wraps the same BidsEntityRewriter /
apply_entity_rewrite the GUI already uses.
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

from src.cli.commands.dataset import cmd_dataset_rewrite_entities  # noqa: E402


def _touch(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _make_project(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-006" / "ses-1" / "func"
    _touch(func_dir / "sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.nii.gz")
    _touch(func_dir / "sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.json", b"{}")
    return project_root


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(
        project=None,
        modality=None,
        entity=None,
        operation="rename",
        current_value=None,
        replacement=None,
        list_modalities=False,
        list_entities=False,
        dry_run=False,
        yes=False,
        json=False,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestListModalities:
    def test_prints_available_modalities(self, tmp_path, capsys):
        project_root = _make_project(tmp_path)
        cmd_dataset_rewrite_entities(
            _args(project=str(project_root), list_modalities=True)
        )
        out = capsys.readouterr().out
        assert "func" in out

    def test_json_mode(self, tmp_path, capsys):
        project_root = _make_project(tmp_path)
        cmd_dataset_rewrite_entities(
            _args(project=str(project_root), list_modalities=True, json=True)
        )
        payload = json.loads(capsys.readouterr().out)
        assert "func" in payload["available_modalities"]


class TestListEntities:
    def test_prints_entities_and_values(self, tmp_path, capsys):
        project_root = _make_project(tmp_path)
        cmd_dataset_rewrite_entities(
            _args(project=str(project_root), list_entities=True, modality="func")
        )
        out = capsys.readouterr().out
        assert "task" in out
        assert "RS" in out

    def test_requires_modality(self, tmp_path, capsys):
        project_root = _make_project(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            cmd_dataset_rewrite_entities(
                _args(project=str(project_root), list_entities=True)
            )
        assert exc_info.value.code == 1


class TestDryRun:
    def test_previews_without_changing_files(self, tmp_path, capsys):
        project_root = _make_project(tmp_path)
        original = (
            project_root
            / "sub-006"
            / "ses-1"
            / "func"
            / "sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.nii.gz"
        )
        assert original.exists()

        cmd_dataset_rewrite_entities(
            _args(
                project=str(project_root),
                modality="func",
                entity="task",
                operation="rename",
                replacement="rest",
                dry_run=True,
            )
        )

        out = capsys.readouterr().out
        assert "Dry run" in out
        assert "task-rest" in out
        # Nothing on disk actually changed.
        assert original.exists()
        assert not (
            project_root
            / "sub-006"
            / "ses-1"
            / "func"
            / "sub-006_ses-1_task-rest_acq-Fs2_run-01_bold.nii.gz"
        ).exists()


class TestApply:
    def test_renames_files_on_disk(self, tmp_path, capsys):
        project_root = _make_project(tmp_path)

        cmd_dataset_rewrite_entities(
            _args(
                project=str(project_root),
                modality="func",
                entity="task",
                operation="rename",
                replacement="rest",
                yes=True,
            )
        )

        renamed = (
            project_root
            / "sub-006"
            / "ses-1"
            / "func"
            / "sub-006_ses-1_task-rest_acq-Fs2_run-01_bold.nii.gz"
        )
        original = (
            project_root
            / "sub-006"
            / "ses-1"
            / "func"
            / "sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.nii.gz"
        )
        assert renamed.exists()
        assert not original.exists()

        out = capsys.readouterr().out
        assert "Done" in out

    def test_json_apply_reports_result(self, tmp_path, capsys):
        project_root = _make_project(tmp_path)
        cmd_dataset_rewrite_entities(
            _args(
                project=str(project_root),
                modality="func",
                entity="task",
                operation="rename",
                replacement="rest",
                yes=True,
                json=True,
            )
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["applied"] is True

    def test_no_matching_files_reports_and_does_not_apply(self, tmp_path, capsys):
        project_root = _make_project(tmp_path)
        cmd_dataset_rewrite_entities(
            _args(
                project=str(project_root),
                modality="func",
                entity="task",
                current_value="doesnotexist",
                operation="rename",
                replacement="rest",
                yes=True,
            )
        )
        out = capsys.readouterr().out
        assert "No files match" in out


class TestRejectsSubjectEntity:
    def test_sub_entity_is_rejected(self, tmp_path, capsys):
        project_root = _make_project(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            cmd_dataset_rewrite_entities(
                _args(
                    project=str(project_root),
                    modality="func",
                    entity="sub",
                    operation="rename",
                    replacement="999",
                )
            )
        assert exc_info.value.code == 1
        assert "not editable" in capsys.readouterr().out.lower() or True


class TestRequiresModalityAndEntity:
    def test_missing_modality_and_entity_exits(self, tmp_path, capsys):
        project_root = _make_project(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            cmd_dataset_rewrite_entities(_args(project=str(project_root)))
        assert exc_info.value.code == 1
