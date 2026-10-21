"""Picker "New folder": one backend function validates the name for every OS
(a folder named `a:b` made on macOS breaks when the dataset reaches Windows)."""
import pytest

from src.folder_create import create_folder


def test_creates_folder_and_returns_its_path(tmp_path):
    made = create_folder(tmp_path, "study")
    assert made == tmp_path / "study" and made.is_dir()


@pytest.mark.parametrize("name", [
    "", "  ", ".", "..", "a/b", "a\b", "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b",
    "tab\tname", "trailing.", "CON", "con.txt", "NUL", "com1", "LPT9",
])
def test_rejects_names_that_break_on_some_os(tmp_path, name):
    with pytest.raises(ValueError):
        create_folder(tmp_path, name)
    assert list(tmp_path.iterdir()) == []


def test_existing_folder_is_an_error(tmp_path):
    (tmp_path / "study").mkdir()
    with pytest.raises(ValueError, match="exists"):
        create_folder(tmp_path, "study")


def test_missing_parent_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="not a folder"):
        create_folder(tmp_path / "gone", "study")


def test_empty_parent_is_an_error_not_the_current_directory():
    with pytest.raises(ValueError, match="not a folder"):
        create_folder("", "study")
