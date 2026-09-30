"""Folder uploads arrive under their relative path; only the file name may be used."""

import pytest

from src.web.blueprints.conversion_utils import upload_basename


@pytest.mark.parametrize(
    "sent, expected",
    [
        ("sub-01_ses-1_task-wb_survey.tsv", "sub-01_ses-1_task-wb_survey.tsv"),
        ("flat/sub-01_ses-1_task-wb_survey.tsv", "sub-01_ses-1_task-wb_survey.tsv"),
        ("deep/er/flat/x.tsv", "x.tsv"),
        ("flat\\sub-01_task-wb_survey.tsv", "sub-01_task-wb_survey.tsv"),  # Windows separators
        ("../../etc/passwd", "passwd"),  # never a way out of the upload folder
        ("", ""),
    ],
)
def test_upload_basename_keeps_only_the_file_name(sent, expected):
    assert upload_basename(sent) == expected
