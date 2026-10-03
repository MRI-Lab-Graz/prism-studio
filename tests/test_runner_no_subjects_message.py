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


# --- metadata-only projects are green; participants without subjects are red ---

import json  # noqa: E402

import pytest  # noqa: E402

from src.runner import validate_dataset  # noqa: E402


def _dataset(root: Path, *, description=True, participants=()):
    if description:
        (root / "dataset_description.json").write_text(
            json.dumps({"Name": "Metadata only", "BIDSVersion": "1.10.0", "DatasetType": "raw"})
        )
    for name in participants:
        (root / name).write_text("participant_id\nsub-01\n" if name.endswith(".tsv") else "{}")
    return root


def _no_subject_errors(root: Path) -> list[str]:
    issues, _stats = validate_dataset(str(root), verbose=False, run_bids=False, run_prism=True)
    return [i[1] for i in issues if i[0] == "ERROR" and "No subjects found" in i[1]]


def test_metadata_only_project_has_no_missing_subjects_error(tmp_path):
    assert _no_subject_errors(_dataset(tmp_path)) == []


@pytest.mark.parametrize("name", ["participants.tsv", "participants.json"])
def test_participants_file_without_subject_folders_is_an_error(tmp_path, name):
    errors = _no_subject_errors(_dataset(tmp_path, participants=[name]))
    assert len(errors) == 1


def test_folder_without_dataset_description_still_says_point_at_the_root(tmp_path):
    errors = _no_subject_errors(_dataset(tmp_path, description=False))
    assert len(errors) == 1 and "dataset root" in errors[0]
