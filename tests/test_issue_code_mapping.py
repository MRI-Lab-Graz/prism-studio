"""Data problems must not surface as PRISM901 ("Internal validation error")."""

import pytest

from src.issues import infer_code_from_message


@pytest.mark.parametrize(
    "message,code",
    [
        ("File sub-01_ses-1_task-brs_survey.tsv is not a valid TSV (no header found).", "PRISM401"),
        ("sub-01_ses-1_task-brs_survey.tsv line 2: Value 'abc' for 'BRS01' is not a valid integer", "PRISM402"),
        ("sub-01_ses-1_task-brs_survey.tsv line 2: Value 'abc' for 'BRS01' is not numeric but has numeric constraints", "PRISM402"),
        ("Session ses-2 appears only in 1/3 subjects", "PRISM601"),
    ],
)
def test_data_problems_have_their_own_code(message, code):
    assert infer_code_from_message(message) == code
