"""The renamer refuses new names that are not a plain file name (preview and copy agree)."""

import pytest

from src.physio_renamer import new_filename_problem


@pytest.mark.parametrize("name", ["sub-01_ses-1_task-x_physio.tsv", "a.b.c", "x" * 200])
def test_plain_names_are_fine(name):
    assert new_filename_problem(name) == ""


@pytest.mark.parametrize("name", ["", "   ", ".", "..", "a/b.tsv", "../x.tsv", "/tmp/x.tsv", "a\\b.tsv", "a\x00b", "x" * 300])
def test_unusable_names_get_a_reason(name):
    assert new_filename_problem(name)
