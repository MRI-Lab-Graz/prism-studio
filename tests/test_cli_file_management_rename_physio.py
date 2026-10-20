"""Tests for `prism_tools.py file-management rename-physio`.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P2) found that the Studio
GUI's physio/eyetracking batch renamer (api_physio_rename in
conversion_physio_handlers.py) had no CLI equivalent, and its rename rules
were only defined as private functions inside that Flask handler file
(since extracted into src.physio_renamer, see the preceding commit).
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
    cmd_file_management_rename_physio,
)


def _args(**overrides) -> SimpleNamespace:
    defaults = dict(
        input=None,
        output=None,
        pattern=None,
        replacement=None,
        id_source="filename",
        folder_subject_level=2,
        folder_session_level=1,
        folder_example_path=None,
        folder_subject_value=None,
        folder_session_value=None,
        modality="physio",
        organize=False,
        apply=False,
        json=False,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestInputValidation:
    def test_missing_input_directory_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cmd_file_management_rename_physio(
                _args(
                    input=str(tmp_path / "does-not-exist"),
                    pattern="^VP_",
                    replacement="clean_",
                )
            )
        assert exc_info.value.code == 1
        assert "not a directory" in capsys.readouterr().out

    def test_empty_input_folder_reports_no_files(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        cmd_file_management_rename_physio(
            _args(input=str(input_dir), pattern="^VP_", replacement="clean_")
        )
        assert "No files found" in capsys.readouterr().out

    def test_invalid_regex_exits(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "VP_001.vpd").write_bytes(b"data")

        with pytest.raises(SystemExit) as exc_info:
            cmd_file_management_rename_physio(
                _args(input=str(input_dir), pattern="(unclosed", replacement="x")
            )
        assert exc_info.value.code == 1
        assert "Error" in capsys.readouterr().out


class TestPreview:
    def test_preview_lists_renames_without_writing(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "VP_001.vpd").write_bytes(b"data")

        cmd_file_management_rename_physio(
            _args(input=str(input_dir), pattern="^VP_", replacement="clean_")
        )

        out = capsys.readouterr().out
        assert "clean_001.vpd" in out
        assert "Preview only" in out

    def test_json_preview(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "VP_001.vpd").write_bytes(b"data")

        cmd_file_management_rename_physio(
            _args(
                input=str(input_dir),
                pattern="^VP_",
                replacement="clean_",
                json=True,
            )
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["applied"] is False
        assert payload["results"][0]["new"] == "clean_001.vpd"

    def test_skips_dotfiles(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "VP_001.vpd").write_bytes(b"data")
        (input_dir / ".hidden").write_bytes(b"data")

        cmd_file_management_rename_physio(
            _args(
                input=str(input_dir),
                pattern="^VP_",
                replacement="clean_",
                json=True,
            )
        )

        payload = json.loads(capsys.readouterr().out)
        assert len(payload["results"]) == 1


class TestApply:
    def test_apply_without_output_exits(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "VP_001.vpd").write_bytes(b"data")

        with pytest.raises(SystemExit) as exc_info:
            cmd_file_management_rename_physio(
                _args(
                    input=str(input_dir),
                    pattern="^VP_",
                    replacement="clean_",
                    apply=True,
                )
            )
        assert exc_info.value.code == 1
        assert "--output is required" in capsys.readouterr().out

    def test_apply_copies_renamed_files(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "VP_001.vpd").write_bytes(b"physio-data")
        output_dir = tmp_path / "out"

        cmd_file_management_rename_physio(
            _args(
                input=str(input_dir),
                output=str(output_dir),
                pattern="^VP_",
                replacement="clean_",
                apply=True,
            )
        )

        renamed = output_dir / "clean_001.vpd"
        assert renamed.exists()
        assert renamed.read_bytes() == b"physio-data"
        # Original file untouched (copy, not move).
        assert (input_dir / "VP_001.vpd").exists()
        assert "Done: 1 file(s) copied" in capsys.readouterr().out

    def test_apply_json_reports_copied_count(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "VP_001.vpd").write_bytes(b"data")
        (input_dir / "VP_002.vpd").write_bytes(b"data")
        output_dir = tmp_path / "out"

        cmd_file_management_rename_physio(
            _args(
                input=str(input_dir),
                output=str(output_dir),
                pattern="^VP_",
                replacement="clean_",
                apply=True,
                json=True,
            )
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["applied"] is True
        assert payload["copied"] == 2

    def test_id_source_folder_uses_subject_session_placeholders(
        self, tmp_path, capsys
    ):
        input_dir = tmp_path / "in"
        (input_dir / "sub-07" / "ses-03").mkdir(parents=True)
        (input_dir / "sub-07" / "ses-03" / "VPDATA.RAW").write_bytes(b"data")
        output_dir = tmp_path / "out"

        cmd_file_management_rename_physio(
            _args(
                input=str(input_dir),
                output=str(output_dir),
                pattern=r"^VPDATA\.RAW$",
                replacement="sub-{subject}_ses-{session}_physio.raw",
                id_source="folder",
                apply=True,
            )
        )

        assert (output_dir / "sub-07_ses-03_physio.raw").exists()

    def test_organize_writes_bids_layout(self, tmp_path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "raw_001.vpd").write_bytes(b"data")
        output_dir = tmp_path / "out"

        cmd_file_management_rename_physio(
            _args(
                input=str(input_dir),
                output=str(output_dir),
                pattern=r"^raw_001\.vpd$",
                replacement="sub-001_recording-ecg_physio.vpd",
                modality="physio",
                organize=True,
                apply=True,
            )
        )

        assert (
            output_dir / "sub-001" / "physio" / "sub-001_recording-ecg_physio.vpd"
        ).exists()

    def test_organize_raw_into_beh_refused(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "raw_001.vpd").write_bytes(b"data")
        output_dir = tmp_path / "out"

        cmd_file_management_rename_physio(
            _args(
                input=str(input_dir),
                output=str(output_dir),
                pattern=r"^raw_001\.vpd$",
                replacement="sub-001_task-rest_physio.vpd",
                modality="beh",
                organize=True,
                apply=True,
            )
        )

        assert "physio batch-convert --destination beh" in capsys.readouterr().out
        assert not (output_dir / "sub-001").exists()

    def test_organize_tsv_gz_into_beh_accepted(self, tmp_path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "raw_001.tsv.gz").write_bytes(b"data")
        output_dir = tmp_path / "out"

        cmd_file_management_rename_physio(
            _args(
                input=str(input_dir),
                output=str(output_dir),
                pattern=r"^raw_001\.tsv\.gz$",
                replacement="sub-001_task-rest_physio.tsv.gz",
                modality="beh",
                organize=True,
                apply=True,
            )
        )

        assert (
            output_dir / "sub-001" / "beh" / "sub-001_task-rest_physio.tsv.gz"
        ).exists()

    def test_organize_task_bound_name_into_physio_refused(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "raw_001.vpd").write_bytes(b"data")
        output_dir = tmp_path / "out"

        cmd_file_management_rename_physio(
            _args(
                input=str(input_dir),
                output=str(output_dir),
                pattern=r"^raw_001\.vpd$",
                replacement="sub-001_task-rest_recording-ecg_physio.vpd",
                modality="physio",
                organize=True,
                apply=True,
            )
        )

        out = capsys.readouterr().out
        assert "beh, func, eeg" in out
        assert not (output_dir / "sub-001").exists()
        assert not list(output_dir.rglob("*.vpd")) if output_dir.exists() else True

    def test_organize_events_refused(self, tmp_path, capsys):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        (input_dir / "raw.tsv").write_bytes(b"data")

        cmd_file_management_rename_physio(
            _args(
                input=str(input_dir),
                output=str(tmp_path / "out"),
                pattern=r"^raw\.tsv$",
                replacement="sub-001_task-rest_events.tsv",
                modality="events",
                organize=True,
                apply=True,
            )
        )

        assert "next to its task in func/, beh/ or eeg/" in capsys.readouterr().out

    def test_parser_accepts_beh_modality(self):
        from src.cli.parser import build_prism_tools_parsers

        parser, _ = build_prism_tools_parsers(APP_ROOT)
        args = parser.parse_args(
            ["file-management", "rename-physio", "--input", "x", "--pattern", "a", "--replacement", "b", "--modality", "beh"]
        )
        assert args.modality == "beh"
