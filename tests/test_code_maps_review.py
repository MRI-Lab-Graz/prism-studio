"""Faults the final review of the code-map branch reproduced (invented codes only)."""

import json
import subprocess

import pytest

from src.code_maps import CodeMapError, is_code_map
from src.git_exclude import SENSITIVE_PATHS, ensure_git_excluded
from tests.test_survey_code_maps import (  # noqa: F401 - `project` is a fixture
    MissingIdMappingError,
    _id_map,
    convert,
    one_file,
    project,
    warnings_of,
    write_map,
    written,
)


@pytest.mark.parametrize("rows", [(), (("AAAA", ""),)])
def test_an_unfilled_map_never_writes_codes_as_subjects(project, rows):  # noqa: F811
    write_map(project, "survey_code_map.tsv", *rows)
    with pytest.raises(MissingIdMappingError):
        convert(project)
    assert written(project) == []


def test_date_numbered_sessions_cannot_use_session_maps_even_with_a_typed_session(project):  # noqa: F811
    (project / "code" / "session_map.json").write_text(json.dumps({"1": "1", "2": "2", "post": "2"}), encoding="utf-8")
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write_map(project, "survey_ses-2_code_map.tsv", ("AAAA", "sub-002"))
    text = "Code,startdate,PSS1\naaaa,2026-01-01 10:00:00,0\naaaa,2026-02-01 10:00:00,1\n"
    with pytest.raises(CodeMapError, match="--session"):
        convert(project, text, session_column=None, session="post", duplicate_handling="sessions")
    assert written(project) == []


def test_near_matched_questionnaires_are_part_of_the_row(project):  # noqa: F811
    library = project / "code" / "library" / "survey" / "survey-ads.json"
    template = json.loads(library.read_text(encoding="utf-8"))
    template["ADS01"] = template.pop("ADS1")
    library.write_text(json.dumps(template), encoding="utf-8")
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write_map(project, "survey_task-ads_code_map.tsv", ("AAAA", "sub-002"))
    with pytest.raises(CodeMapError, match="different participants"):
        convert(project, allow_near_item_match=True)


def test_a_chosen_id_column_is_not_swapped_for_one_that_matches_better(project):  # noqa: F811
    write_map(project, "survey_code_map.tsv", ("1", "sub-009"), ("2", "sub-008"))
    with pytest.raises(MissingIdMappingError) as error:
        convert(project, "Code,id,session,PSS1\n7,1,pre,0\n8,2,pre,1\n")
    assert error.value.missing_ids == ["7", "8"]


def test_id_map_rows_with_an_empty_side_are_skipped(project):  # noqa: F811
    path = project.parent / "ids.tsv"
    path.write_text("code\tparticipant_id\n\tsub-002\n\tsub-003\nBBBB\t\nAAAA\tsub-001\n", encoding="utf-8")
    convert(project, id_map_file=path)
    assert written(project)[0].startswith("sub-001/")


def _ignored(repo, path):
    return subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", path]).returncode == 0


def test_a_project_inside_a_larger_repository_is_protected(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    study = tmp_path / "study"
    (study / "code").mkdir(parents=True)
    (study / "code" / "survey_code_map.tsv").write_text("x")
    ensure_git_excluded(study, *SENSITIVE_PATHS)
    assert _ignored(tmp_path, "study/code/survey_code_map.tsv")
    assert not _ignored(tmp_path, "code/survey_code_map.tsv")


def test_capitalised_names_are_ignored_by_case_sensitive_git(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "core.ignorecase", "false"], check=True)
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "Survey_Code_Map.tsv").write_text("x")
    ensure_git_excluded(tmp_path, *SENSITIVE_PATHS)
    assert _ignored(tmp_path, "code/Survey_Code_Map.tsv")


def test_maps_are_excluded_even_when_id_map_is_used(project):  # noqa: F811
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    convert(project, id_map_file=_id_map(project, ("AAAA", "sub-005")))
    assert _ignored(project, "code/survey_code_map.tsv")


def test_pre_checks_do_not_map_participants(project):  # noqa: F811
    from src.code_maps import without_project_code_maps

    write_map(project, "survey_code_map.tsv", ("ZZZZ", "sub-001"))
    with without_project_code_maps():
        convert(project, "Code,session,PSS1\naaaa,pre,0\n", dry_run=True)
    with pytest.raises(MissingIdMappingError):
        convert(project, "Code,session,PSS1\naaaa,pre,0\n", dry_run=True)


def test_both_survey_pre_checks_run_without_code_maps():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "src" / "survey_input_checks.py").read_text(encoding="utf-8")
    assert source.count("with without_project_code_maps():") == 2


def test_a_folder_named_like_a_map_is_left_out_too():
    assert is_code_map(("code", "survey_code_map_backup", "old.tsv"))


def test_a_task_name_in_the_wrong_case_stops(project):  # noqa: F811
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write_map(project, "survey_task-ADS_code_map.tsv", ("AAAA", "sub-002"))
    with pytest.raises(CodeMapError, match="task-ads"):
        convert(project)


def test_a_session_the_project_does_not_use_warns(project):  # noqa: F811
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write_map(project, "survey_ses-pre_code_map.tsv", ("AAAA", "sub-002"))
    assert "Code map survey_ses-pre_code_map.tsv: the project has no session 'pre'." in warnings_of(convert(project))
    assert written(project)[0] == one_file("sub-001", "ses-1", "ads")


def test_a_linked_worktree_is_protected_without_running_git(tmp_path, monkeypatch):
    main, linked = tmp_path / "main", tmp_path / "linked"
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    run = ["git", "-C", str(main), "-c", "user.name=a", "-c", "user.email=a@b.c"]
    subprocess.run([*run, "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    subprocess.run([*run, "worktree", "add", "-q", str(linked)], check=True)
    (linked / "code").mkdir()
    (linked / "code" / "survey_code_map.tsv").write_text("x")
    with monkeypatch.context() as patched:
        patched.setattr(subprocess, "run", lambda *a, **k: pytest.fail("excluding must not start a process"))
        ensure_git_excluded(linked, *SENSITIVE_PATHS)
    assert _ignored(linked, "code/survey_code_map.tsv")
