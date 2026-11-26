"""ProjectCodeMaps: the one way importers apply a project's code maps (invented codes only)."""

import json
import subprocess

import pytest

from src.code_maps import ProjectCodeMaps, UnknownCodeError, without_project_code_maps


@pytest.fixture
def root(tmp_path):
    (tmp_path / "code").mkdir()
    (tmp_path / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "multiple"}}), encoding="utf-8")
    (tmp_path / "code" / "session_map.json").write_text(json.dumps({"pre": "1"}), encoding="utf-8")
    return tmp_path


def write_map(root, name, *rows):
    (root / "code" / name).write_text(
        "code\tparticipant_id\n" + "".join(f"{c}\t{p}\n" for c, p in rows), encoding="utf-8"
    )


def test_open_without_project_maps_or_while_ignored_is_none(root):
    assert ProjectCodeMaps.open(None, "biometrics") is None
    assert ProjectCodeMaps.open(root, "biometrics") is None
    write_map(root, "survey_code_map.tsv", ("AAAA", "sub-001"))
    assert ProjectCodeMaps.open(root, "biometrics") is None
    write_map(root, "biometrics_code_map.tsv", ("AAAA", "sub-001"))
    with without_project_code_maps():
        assert ProjectCodeMaps.open(root, "biometrics") is None


def test_open_excludes_the_maps_from_git_even_for_another_modality(root):
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    write_map(root, "survey_code_map.tsv", ("AAAA", "sub-001"))
    ProjectCodeMaps.open(root, "biometrics")
    out = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-uall"], capture_output=True, text=True)
    assert "code_map" not in out.stdout


def test_every_unknown_value_is_reported_at_once(root):
    write_map(root, "biometrics_code_map.tsv", ("AAAA", "sub-001"))
    maps = ProjectCodeMaps.open(root, "biometrics")
    with pytest.raises(UnknownCodeError) as error:
        maps.resolve_all([("ZZZZ", (), None), ("aaaa", (), None), ("BBBB", (), None)])
    assert error.value.codes == ["BBBB", "ZZZZ"]
    assert str(error.value) == "ID mapping incomplete: 2 IDs from data are missing in the mapping: BBBB, ZZZZ."


def test_an_unfilled_map_lists_nothing(root):
    write_map(root, "biometrics_code_map.tsv")
    with pytest.raises(UnknownCodeError):
        ProjectCodeMaps.open(root, "biometrics").resolve_all([("AAAA", (), None)])


def test_keep_targets_lets_a_participant_number_stay(root):
    write_map(root, "physio_code_map.tsv", ("AAAA", "sub-004"))
    maps = ProjectCodeMaps.open(root, "physio")
    rows = [("004", (), None), ("sub-004", (), None), ("aaaa", (), None)]
    assert maps.resolve_all(rows, keep_targets=True) == ["sub-004"] * 3
    with pytest.raises(UnknownCodeError):
        maps.resolve_all(rows[:1])


def test_notes_warnings_first_then_the_files_used(root):
    write_map(root, "biometrics_code_map.tsv", ("AAAA", "sub-001"), ("BBBB", "sub-002"))
    write_map(root, "biometrics_task-nope_code_map.tsv", ("AAAA", "sub-001"))
    write_map(root, "biometrics_ses-9_code_map.tsv", ("AAAA", "sub-001"))
    maps = ProjectCodeMaps.open(root, "biometrics", known_tasks={"grip"})
    maps.resolve_all([("aaaa", ("grip",), "ses-1"), ("BBBB", ("grip",), "1"), ("AAAA ", ("grip",), "1")])
    assert maps.notes() == [
        "Code map biometrics_ses-9_code_map.tsv: the project has no session '9'.",
        "Code map biometrics_task-nope_code_map.tsv: no template for task 'nope'.",
        "Applied code map biometrics_code_map.tsv: 2 code(s).",
    ]


def test_a_task_written_in_the_wrong_case_stops(root):
    write_map(root, "biometrics_task-Grip_code_map.tsv", ("AAAA", "sub-001"))
    with pytest.raises(ValueError, match="task-grip"):
        ProjectCodeMaps.open(root, "biometrics", known_tasks={"grip"})
