import pytest

from src.schema_manager import (
    is_compatible_version,
    parse_version,
    validate_schema_version,
)

SCHEMA = {"_validator_info": {"schema_version": "2.1.0"}}


def _issues(meta_version):
    return validate_schema_version({"Metadata": {"SchemaVersion": meta_version}}, SCHEMA)


@pytest.mark.parametrize("provided", ["2.0.0", "2.0.9", "2.1.0", "2.1.5", "2.7.0"])
def test_same_major_never_warns(provided):
    assert _issues(provided) == []


@pytest.mark.parametrize("provided", ["1.9.9", "3.0.0", "0.0.1"])
def test_other_major_still_warns(provided):
    ((level, message),) = _issues(provided)
    assert level == "WARNING" and "mismatch" in message.lower() and provided in message


@pytest.mark.parametrize("provided", ["2.1", "2", "abc", "", "v2.0.0", 5, ["2.0.0"], None])
def test_odd_versions_never_raise(provided):
    _issues(provided)  # must not raise
    assert isinstance(is_compatible_version("2.1.0", provided), bool)


def test_two_part_version_is_read_as_major_minor_zero():
    assert parse_version("2.1") == (2, 1, 0) and parse_version("2.1.4.9") == (2, 1, 4)
    assert is_compatible_version("2.1.0", "2.0") is True


def test_unparseable_versions_warn():
    for bad in ("abc", "v2.0.0", 5):
        assert _issues(bad) != []  # (0,0,0) is another major


def test_a_pinned_older_schema_matches_its_own_files():
    pinned = {"_validator_info": {"schema_version": "2.0.0"}}
    assert (
        validate_schema_version({"Metadata": {"SchemaVersion": "2.0.0"}}, pinned) == []
    )


def test_no_version_declared_is_no_issue():
    assert validate_schema_version({"Metadata": {}}, SCHEMA) == []
