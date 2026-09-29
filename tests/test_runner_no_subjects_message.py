"""No sub-* folders is one clear error, not a participants.tsv "mismatch"."""

from pathlib import Path

from src.runner import (
    _check_participants_subject_alignment,
    _has_subject_dirs,
    _no_subjects_message,
)


def _project(tmp_path: Path, participants: list[str]) -> Path:
    if participants:
        rows = ["participant_id"] + participants
        (tmp_path / "participants.tsv").write_text("\n".join(rows) + "\n")
    return tmp_path


def test_registered_participants_but_no_folders_is_not_a_mismatch(tmp_path):
    root = _project(tmp_path, ["sub-01", "sub-02"])

    assert not _has_subject_dirs(str(root))
    assert _check_participants_subject_alignment(str(root)) == []
    message = _no_subjects_message(str(root))
    assert message.startswith("No subjects found in dataset")
    assert "lists 2 participant(s)" in message


def test_empty_dataset_keeps_dataset_root_hint(tmp_path):
    message = _no_subjects_message(str(tmp_path))

    assert message.startswith("No subjects found in dataset")
    assert "dataset root" in message


def test_real_mismatch_is_still_reported(tmp_path):
    root = _project(tmp_path, ["sub-01"])
    (root / "sub-02").mkdir()

    issues = _check_participants_subject_alignment(str(root))

    assert len(issues) == 1
    assert "mismatch" in issues[0][1]
