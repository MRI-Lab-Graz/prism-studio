from flask import Flask

from src.web.blueprints.conversion_participants_convert import (
    _check_existing_participants_files,
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
