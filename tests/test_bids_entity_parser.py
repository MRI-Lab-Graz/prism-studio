from pathlib import Path

from src.bids_entity_parser import BidsEntityParser


def test_parse_entity_token_normalizes_key() -> None:
    assert BidsEntityParser.parse_entity_token("Task-rest") == ("task", "rest")


def test_parse_entity_token_rejects_invalid_value() -> None:
    assert BidsEntityParser.parse_entity_token("task-resting-state") is None


def test_subject_and_session_dir_helpers_strip_prefixes() -> None:
    assert BidsEntityParser.subject_label_from_dir("sub-001") == "001"
    assert BidsEntityParser.session_label_from_dir("ses-baseline") == "baseline"


def test_extract_subject_from_path_returns_first_subject_segment() -> None:
    assert (
        BidsEntityParser.extract_subject_from_path(
            Path("project") / "sub-001" / "ses-01" / "func" / "file.nii.gz"
        )
        == "sub-001"
    )