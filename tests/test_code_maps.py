"""Reading and resolving project code maps (invented codes only)."""

import pytest

from src.code_maps import CodeMapError, load_code_maps, resolve_row

HEADER = "code\tparticipant_id\n"


def write(root, name, *rows, text=None, encoding="utf-8"):
    (root / "code").mkdir(parents=True, exist_ok=True)
    body = text if text is not None else HEADER + "".join(f"{c}\t{p}\n" for c, p in rows)
    (root / "code" / name).write_bytes(body.encode(encoding))


def resolve(root, code, tasks=("ads",), session=None):
    hit = resolve_row(load_code_maps(root, "survey"), code, tasks, session)
    return hit and hit[0]


@pytest.fixture
def two_maps(tmp_path):
    write(tmp_path, "survey_code_map.tsv", ("AAAA", "sub-001"), ("BBBB", "sub-002"))
    write(tmp_path, "survey_task-ads_code_map.tsv", ("AAAA", "sub-009"))
    return tmp_path


def test_narrow_file_wins_and_the_rest_falls_back(two_maps):
    assert resolve(two_maps, "aaaa ") == "sub-009"
    assert resolve(two_maps, "BBBB") == "sub-002"
    assert resolve(two_maps, "AAAA", ["pss"]) == "sub-001"
    assert resolve(two_maps, "ZZZZ") is None
    assert resolve(two_maps, "AAAA", []) == "sub-001"


def test_the_files_used_are_named(two_maps):
    maps = load_code_maps(two_maps, "survey")
    assert resolve_row(maps, "AAAA", ["ads"], None) == ("sub-009", ("survey_task-ads_code_map.tsv",))


def test_tasks_of_one_row_must_agree(two_maps):
    with pytest.raises(CodeMapError) as error:
        resolve(two_maps, "AAAA", ["ads", "pss"])
    for part in ("AAAA", "ads", "pss", "sub-001", "sub-009", "survey_code_map.tsv", "survey_task-ads_code_map.tsv"):
        assert part in str(error.value)


def test_a_task_without_an_entry_makes_the_row_unlisted(tmp_path):
    write(tmp_path, "survey_task-ads_code_map.tsv", ("AAAA", "sub-001"))
    assert resolve(tmp_path, "AAAA", ["ads", "pss"]) is None


def test_task_and_session_beats_either_alone(tmp_path):
    write(tmp_path, "survey_task-ads_code_map.tsv", ("AAAA", "sub-001"))
    write(tmp_path, "survey_ses-3_code_map.tsv", ("AAAA", "sub-002"))
    write(tmp_path, "survey_task-ads_ses-3_code_map.tsv", ("AAAA", "sub-003"))
    assert resolve(tmp_path, "AAAA", session="ses-3") == "sub-003"


def test_task_and_session_files_must_agree(tmp_path):
    write(tmp_path, "survey_task-ads_code_map.tsv", ("AAAA", "sub-001"))
    write(tmp_path, "survey_ses-3_code_map.tsv", ("AAAA", "sub-002"))
    with pytest.raises(CodeMapError) as error:
        resolve(tmp_path, "AAAA", session="3")
    assert "survey_task-ads_code_map.tsv" in str(error.value) and "survey_ses-3_code_map.tsv" in str(error.value)
    write(tmp_path, "survey_ses-3_code_map.tsv", ("AAAA", "sub-001"))
    assert resolve(tmp_path, "AAAA", session="3") == "sub-001"


def test_session_labels_are_exact_strings(tmp_path):
    write(tmp_path, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write(tmp_path, "survey_ses-1_code_map.tsv", ("AAAA", "sub-002"))
    assert resolve(tmp_path, "AAAA", session="01") == "sub-001"
    assert resolve(tmp_path, "AAAA", session="ses-1") == "sub-002"


def test_a_session_file_needs_a_session(tmp_path):
    write(tmp_path, "survey_code_map.tsv", ("AAAA", "sub-001"), ("BBBB", "sub-002"))
    write(tmp_path, "survey_ses-1_code_map.tsv", ("AAAA", "sub-009"))
    with pytest.raises(CodeMapError, match="--session"):
        resolve(tmp_path, "AAAA")
    assert resolve(tmp_path, "BBBB") == "sub-002"


def test_one_code_twice(tmp_path):
    write(tmp_path, "survey_code_map.tsv", ("AAAA", "sub-001"), ("aaaa", "sub-001"))
    assert resolve(tmp_path, "AAAA") == "sub-001"
    write(tmp_path, "survey_code_map.tsv", ("AAAA", "sub-001"), ("aaaa", "sub-002"))
    with pytest.raises(CodeMapError, match="survey_code_map.tsv"):
        load_code_maps(tmp_path, "survey")


@pytest.mark.parametrize("name", [
    "survey_taks-ads_code_map.tsv",
    "survey_ses-3_task-ads_code_map.tsv",
    "survey_run-1_code_map.tsv",
    "survey_code_map - Kopie.tsv",
])
def test_names_that_do_not_parse_stop(tmp_path, name):
    write(tmp_path, name, ("AAAA", "sub-001"))
    with pytest.raises(CodeMapError, match=name):
        load_code_maps(tmp_path, "survey")


@pytest.mark.parametrize("name", ["survey_code_map.csv", "Survey_Code_Map.tsv"])
def test_near_names_stop_with_the_expected_name(tmp_path, name):
    write(tmp_path, name, ("AAAA", "sub-001"))
    with pytest.raises(CodeMapError, match="survey_code_map.tsv"):
        load_code_maps(tmp_path, "survey")


def test_other_modalities_and_subfolders_are_not_loaded(tmp_path):
    write(tmp_path, "biometrics_code_map.tsv", ("AAAA", "sub-001"))
    (tmp_path / "code" / "old").mkdir()
    (tmp_path / "code" / "old" / "survey_code_map.tsv").write_text(HEADER + "AAAA\tsub-001\n")
    assert load_code_maps(tmp_path, "survey") == []
    assert load_code_maps(tmp_path / "nowhere", "survey") == []


def test_columns_are_read_by_name_not_position(tmp_path):
    write(tmp_path, "survey_code_map.tsv", text="participant_id\tcode\nsub-001\tAAAA\n")
    assert resolve(tmp_path, "AAAA") == "sub-001"


def test_a_missing_header_stops(tmp_path):
    write(tmp_path, "survey_code_map.tsv", text="AAAA\tsub-001\n")
    with pytest.raises(CodeMapError, match="participant_id"):
        load_code_maps(tmp_path, "survey")


def test_excel_files_and_empty_rows(tmp_path):
    write(tmp_path, "survey_code_map.tsv", text="﻿code\tparticipant_id\r\nAAAA\tsub-001\r\nBBBB\t\r\nCCCC\r\n")
    assert resolve(tmp_path, "AAAA") == "sub-001"
    assert resolve(tmp_path, "BBBB") is None
    assert resolve(tmp_path, "CCCC") is None


def test_participant_ids_with_and_without_prefix_are_one(tmp_path):
    write(tmp_path, "survey_task-ads_code_map.tsv", ("AAAA", "004"))
    write(tmp_path, "survey_ses-1_code_map.tsv", ("AAAA", "sub-004"))
    assert resolve(tmp_path, "AAAA", session="1") == "sub-004"


@pytest.mark.parametrize("body", [b"\xff\xfe\x00bad", b""])
def test_unreadable_files_are_reported_not_crashed(tmp_path, body):
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "survey_code_map.tsv").write_bytes(body)
    with pytest.raises(CodeMapError, match="survey_code_map.tsv"):
        load_code_maps(tmp_path, "survey")


def test_a_participant_id_that_is_a_path_stops(tmp_path):
    write(tmp_path, "survey_code_map.tsv", ("AAAA", "../../x"))
    with pytest.raises(CodeMapError, match="survey_code_map.tsv"):
        load_code_maps(tmp_path, "survey")
