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


@pytest.mark.parametrize("provided", ["", None, "2.1", "2"])
def test_no_or_same_major_odd_versions_give_no_issue(provided):
    assert _issues(provided) == []
    assert isinstance(is_compatible_version("2.1.0", provided), bool)


@pytest.mark.parametrize("provided", ["abc", "v2.0.0", 5, ["2.0.0"]])
def test_unreadable_versions_give_one_warning_and_never_raise(provided):
    ((level, _),) = _issues(provided)
    assert level == "WARNING"
    assert isinstance(is_compatible_version("2.1.0", provided), bool)


@pytest.mark.parametrize("provided", ["abc", "v2.0.0", 5, ["2.0.0"]])
def test_unreadable_version_is_reported_as_unreadable_not_as_another_major(provided):
    ((_, message),) = _issues(provided)
    assert "Schema version mismatch" in message
    assert "unreadable" in message
    assert "different major version" not in message
    assert "vv2" not in message


def test_a_readable_other_major_still_says_different_major_version():
    ((_, message),) = _issues("1.9.9")
    assert "different major version" in message and "unreadable" not in message


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


def test_a_sidecar_with_an_older_minor_version_passes_the_whole_validator(tmp_path):
    from src.validation_matrix import NONE, SIDECAR, Defect, _json, build_clean_project, run_matrix

    clean = tmp_path / "control"
    build_clean_project(clean)
    older = Defect(
        "sidecar_older_minor",
        "the sidecar declares an older minor schema version",
        NONE,
        _json(SIDECAR, lambda d: d["Metadata"].__setitem__("SchemaVersion", "2.0.0")),
    )
    row = run_matrix(clean, [older])["rows"][0]
    assert row["got"] == [], row
