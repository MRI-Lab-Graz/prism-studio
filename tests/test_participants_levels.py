"""Coded participants columns need value labels (Levels) in participants.json."""

import json

import pytest
from src.issues import infer_code_from_message

from src.participants_levels import check_participants_levels


def _project(tmp_path, columns: dict[str, list[str]], sidecar: dict):
    n = len(next(iter(columns.values())))
    header = "\t".join(["participant_id", *columns])
    rows = [
        "\t".join([f"sub-{i:02d}", *(col[i] for col in columns.values())])
        for i in range(n)
    ]
    (tmp_path / "participants.tsv").write_text("\n".join([header, *rows]) + "\n")
    (tmp_path / "participants.json").write_text(json.dumps(sidecar))
    return str(tmp_path)


def test_coded_column_without_levels_is_a_warning(tmp_path):
    root = _project(tmp_path, {"sex": ["1", "2", "1"]}, {"sex": {"Description": "Sex"}})

    issues = check_participants_levels(root)

    assert len(issues) == 1
    severity, message, path = issues[0]
    assert severity == "WARNING"
    assert "'sex'" in message
    assert path.endswith("participants.json")


def test_complete_levels_pass(tmp_path):
    root = _project(
        tmp_path,
        {"sex": ["1", "2", "1"]},
        {"sex": {"Levels": {"1": "male", "2": "female"}}},
    )

    assert check_participants_levels(root) == []


def test_levels_missing_a_value_is_an_error_naming_the_value(tmp_path):
    root = _project(
        tmp_path,
        {"education": ["3", "4", "5"]},
        {"education": {"Levels": {"3": "a", "4": "b"}}},
    )

    issues = check_participants_levels(root)

    assert len(issues) == 1
    severity, message, _ = issues[0]
    assert severity == "ERROR"
    assert "'education'" in message and "5" in message


@pytest.mark.parametrize(
    "values, sidecar",
    [
        (["19", "24", "31"], {"age": {"Unit": "years"}}),  # declared continuous
        (["1.5", "2.5", "1.5"], {}),  # non-integer numbers are not codes
        ([str(i) for i in range(11)], {}),  # too many distinct values for a code
        (["1", "n/a", "1"], {"age": {"Levels": {"1": "x"}}}),  # n/a is no value
    ],
)
def test_columns_that_are_not_coded_are_not_flagged(tmp_path, values, sidecar):
    root = _project(tmp_path, {"age": values}, sidecar)

    assert check_participants_levels(root) == []


def test_missing_sidecar_flags_coded_columns(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\tsex\nsub-01\t1\n")

    issues = check_participants_levels(str(tmp_path))

    assert [i[0] for i in issues] == ["WARNING"]


def test_no_participants_tsv_is_not_this_checks_business(tmp_path):
    assert check_participants_levels(str(tmp_path)) == []


def test_messages_get_their_own_issue_code(tmp_path):
    root = _project(tmp_path, {"sex": ["1", "2"]}, {})
    _, message, _ = check_participants_levels(root)[0]

    assert infer_code_from_message(message) == "PRISM709"


def test_validator_reports_unlabeled_codes(tmp_path):
    from src.runner import validate_dataset

    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": "1.10.1"})
    )
    (tmp_path / "sub-01").mkdir()
    root = _project(tmp_path, {"sex": ["1", "2"]}, {"sex": {"Description": "Sex"}})

    issues, _ = validate_dataset(root, run_bids=False, run_prism=True)

    assert any("value labels" in str(i[1]) for i in issues)


def test_add_missing_levels_labels_new_codes_with_the_code():
    import pandas as pd

    from src.participants_levels import add_missing_levels

    schema = {
        "education": {"Levels": {"4": "Bachelor"}},
        "weight": {"Description": "no levels, left alone"},
    }
    df = pd.DataFrame(
        {"education": ["4", "6", "-oth-", "n/a", None], "weight": ["55", "60", "1", "2", "3"]}
    )

    add_missing_levels(schema, df)

    assert schema["education"]["Levels"] == {"4": "Bachelor", "6": "6", "-oth-": "-oth-"}
    assert "Levels" not in schema["weight"]
