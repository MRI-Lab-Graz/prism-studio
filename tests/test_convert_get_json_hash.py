"""Regression test for get_json_hash: it must hash actual file content.

A prior version passed `usedforsecurity=(False if ... else canonical.encode(...))`
to hashlib.md5 -- since `usedforsecurity` is keyword-only and never the data
argument, this always hashed b"" regardless of file content, making every
JSON file collide on the same hash (MD5 of the empty string).
"""

from app.src.cli.commands.convert import get_json_hash


def test_get_json_hash_differs_for_different_content(tmp_path):
    file_a = tmp_path / "a.json"
    file_b = tmp_path / "b.json"
    file_a.write_text('{"value": 1}', encoding="utf-8")
    file_b.write_text('{"value": 2}', encoding="utf-8")

    assert get_json_hash(file_a) != get_json_hash(file_b)


def test_get_json_hash_stable_for_semantically_equal_content(tmp_path):
    file_a = tmp_path / "a.json"
    file_b = tmp_path / "b.json"
    file_a.write_text('{"x": 1, "y": 2}', encoding="utf-8")
    file_b.write_text('{"y": 2, "x": 1}', encoding="utf-8")

    assert get_json_hash(file_a) == get_json_hash(file_b)


def test_get_json_hash_not_empty_string_hash(tmp_path):
    empty_md5 = "d41d8cd98f00b204e9800998ecf8427e"
    file_a = tmp_path / "a.json"
    file_a.write_text('{"value": 1}', encoding="utf-8")

    assert get_json_hash(file_a) != empty_md5
