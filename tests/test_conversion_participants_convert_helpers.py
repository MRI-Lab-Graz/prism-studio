import json
import tempfile
from pathlib import Path

import pandas as pd
from flask import Flask

from src.web.blueprints.conversion_participants_convert import (
    _check_existing_participants_files,
    _write_participants_outputs,
)


def test_no_existing_files_returns_no_error(tmp_path):
    participants_tsv, participants_json, existing_files, error_response = (
        _check_existing_participants_files(tmp_path, mode="file", force_overwrite=False)
    )

    assert participants_tsv == tmp_path / "participants.tsv"
    assert participants_json == tmp_path / "participants.json"
    assert existing_files == []
    assert error_response is None


def test_existing_tsv_without_force_overwrite_blocks_with_409(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\n")

    with Flask(__name__).app_context():
        _, _, existing_files, error_response = _check_existing_participants_files(
            tmp_path, mode="file", force_overwrite=False
        )

    assert existing_files == [str(tmp_path / "participants.tsv")]
    assert error_response is not None
    _, status_code = error_response
    assert status_code == 409


def test_existing_tsv_with_force_overwrite_allows_proceed():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        (project_root / "participants.tsv").write_text("participant_id\n")

        _, _, existing_files, error_response = _check_existing_participants_files(
            project_root, mode="file", force_overwrite=True
        )

        assert existing_files == [str(project_root / "participants.tsv")]
        assert error_response is None


def test_existing_mode_bypasses_force_overwrite_requirement(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\n")

    _, _, existing_files, error_response = _check_existing_participants_files(
        tmp_path, mode="existing", force_overwrite=False
    )

    assert error_response is None


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def test_write_participants_outputs_creates_tsv_and_json():
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        source = project_root / "participants_source.csv"
        _write_csv(source, [{"ID": "001", "age": "21"}, {"ID": "002", "age": "22"}])

        mapping = {
            "version": "1.0",
            "mappings": {
                "age": {
                    "source_column": "age",
                    "standard_variable": "age",
                    "type": "string",
                }
            },
        }
        participants_tsv = project_root / "participants.tsv"
        participants_json = project_root / "participants.json"
        logs = []

        result = _write_participants_outputs(
            project_root=project_root,
            input_path=source,
            mapping=mapping,
            converter_separator="auto",
            sheet_arg=0,
            participants_tsv=participants_tsv,
            participants_json=participants_json,
            neurobagel_schema={},
            existing_files=[],
            log_msg=lambda level, message: logs.append((level, message)),
        )

        assert result["status"] == "success"
        assert result["files_created"] == [str(participants_tsv), str(participants_json)]
        assert result["overwrote_existing"] is False
        assert participants_tsv.exists()

        written = json.loads(participants_json.read_text())
        assert "participant_id" in written
        assert written["participant_id"]["Description"] == "Participant identifier (sub-<label>)"


def test_write_participants_outputs_raises_on_conversion_failure():
    import pytest

    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        source = project_root / "participants_source.csv"
        # No ID-like column at all -- matches the proven failure fixture in
        # tests/test_participants_converter_edge_cases.py::
        # test_convert_fails_without_recoverable_participant_id. A column
        # named "ID" with blank values instead gets its blank rows dropped
        # (success=True, fewer rows), not a hard failure -- don't use that.
        _write_csv(source, [{"age": "21"}, {"age": "22"}])

        mapping = {
            "version": "1.0",
            "mappings": {
                "age": {
                    "source_column": "age",
                    "standard_variable": "age",
                    "type": "string",
                }
            },
        }

        with pytest.raises(ValueError, match="Conversion failed"):
            _write_participants_outputs(
                project_root=project_root,
                input_path=source,
                mapping=mapping,
                converter_separator="auto",
                sheet_arg=0,
                participants_tsv=project_root / "participants.tsv",
                participants_json=project_root / "participants.json",
                neurobagel_schema={},
                existing_files=[],
                log_msg=lambda level, message: None,
            )
