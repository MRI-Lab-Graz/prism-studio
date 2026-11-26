"""Survey import finds the project's code maps (invented codes only)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.code_maps import CodeMapError  # noqa: E402
from src.converters.survey import MissingIdMappingError, convert_survey_file_to_prism_dataset  # noqa: E402
from tests.template_fixtures import complete  # noqa: E402


def _template(task):
    item = f"{task.upper()}1"
    return complete({
        "I18n": {"DefaultLanguage": "de"},
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "de"},
        "Study": {"TaskName": task, "OriginalName": task, "LicenseID": "Other", "License": ""},
        "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2026-10-01", "Creator": "t"},
        item: {
            "Description": {"de": "Frage", "en": "Question"},
            "Levels": {"0": {"de": "nie", "en": "never"}, "1": {"de": "oft", "en": "often"}},
        },
    }, task)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    library = root / "code" / "library" / "survey"
    library.mkdir(parents=True)
    for task in ("ads", "pss"):
        (library / f"survey-{task}.json").write_text(json.dumps(_template(task)), encoding="utf-8")
    (root / "project.json").write_text(
        json.dumps({"Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
                    "StudyDesign": {"Timepoints": "multiple"}}),
        encoding="utf-8",
    )
    (root / "code" / "session_map.json").write_text(json.dumps({"pre": "1", "post": "2"}), encoding="utf-8")
    return root


def write_map(project, name, *rows):
    (project / "code" / name).write_text(
        "code\tparticipant_id\n" + "".join(f"{c}\t{p}\n" for c, p in rows), encoding="utf-8"
    )


def convert(project, text="Code,session,PSS1,ADS1\naaaa,pre,0,1\n", **overrides):
    table = project.parent / "data.csv"
    table.write_text(text, encoding="utf-8")
    kwargs = dict(
        input_path=table, library_dir=project / "code" / "library" / "survey", output_root=project,
        id_column="Code", session_column="session", unknown="ignore", force=True, language="en",
        project_path=project,
    )
    kwargs.update(overrides)
    return convert_survey_file_to_prism_dataset(**kwargs)


def written(project):
    return sorted(p.relative_to(project).as_posix() for p in project.glob("sub-*/ses-*/survey/*.tsv"))


def one_file(sub, ses, task):
    return f"{sub}/{ses}/survey/{sub}_{ses}_task-{task}_survey.tsv"


def warnings_of(result):
    return "\n".join(result.conversion_warnings)


def test_project_map_is_applied_without_id_map(project):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    result = convert(project)
    assert written(project) == [one_file("sub-001", "ses-1", "ads"), one_file("sub-001", "ses-1", "pss")]
    assert "Applied code map survey_code_map.tsv: 1 code(s)." in warnings_of(result)


def test_session_scope_uses_the_written_label(project):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write_map(project, "survey_ses-2_code_map.tsv", ("AAAA", "sub-002"))
    convert(project, "Code,session,PSS1\naaaa,pre,0\naaaa,post,1\n")
    assert written(project) == [one_file("sub-001", "ses-1", "pss"), one_file("sub-002", "ses-2", "pss")]


@pytest.mark.parametrize("selected", [None, "pss"])
def test_split_row_stops_and_writes_nothing(project, selected):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write_map(project, "survey_task-ads_code_map.tsv", ("AAAA", "sub-009"))
    with pytest.raises(CodeMapError, match="different participants"):
        convert(project, survey=selected)
    assert written(project) == []


def test_task_map_works_for_its_own_file(project):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write_map(project, "survey_task-ads_code_map.tsv", ("AAAA", "sub-009"))
    convert(project, "Code,session,ADS1\naaaa,pre,1\n")
    assert written(project) == [one_file("sub-009", "ses-1", "ads")]


def test_session_scope_without_session_stops(project):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write_map(project, "survey_ses-1_code_map.tsv", ("AAAA", "sub-002"))
    with pytest.raises(CodeMapError, match="--session"):
        convert(project, "Code,PSS1\naaaa,0\n", session_column=None, duplicate_handling="sessions")
    assert written(project) == []


def test_a_typed_session_counts_for_session_maps(project):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write_map(project, "survey_ses-2_code_map.tsv", ("AAAA", "sub-002"))
    convert(project, "Code,PSS1\naaaa,0\n", session_column=None, session="post")
    assert written(project) == [one_file("sub-002", "ses-2", "pss")]


def test_single_timepoint_project_is_session_1(project):
    (project / "project.json").write_text(
        json.dumps({"Basics": {"Name": "N"}, "StudyDesign": {"Timepoints": "single"}}), encoding="utf-8"
    )
    write_map(project, "survey_ses-1_code_map.tsv", ("AAAA", "sub-001"))
    convert(project, "Code,session,PSS1\naaaa,pre,0\n")
    assert written(project) == [one_file("sub-001", "ses-1", "pss")]


def _id_map(project, *rows):
    path = project.parent / "ids.tsv"
    path.write_text("code\tparticipant_id\n" + "".join(f"{c}\t{p}\n" for c, p in rows), encoding="utf-8")
    return path


def test_id_map_overrides_project_maps(project):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    result = convert(project, id_map_file=_id_map(project, ("AAAA", "sub-005")))
    assert written(project)[0].startswith("sub-005/")
    assert "--id-map given: project code maps not used: survey_code_map.tsv." in warnings_of(result)


def test_id_map_with_a_code_twice_stops(project):
    with pytest.raises(ValueError, match="two different participants"):
        convert(project, id_map_file=_id_map(project, ("AAAA", "sub-005"), ("aaaa", "sub-006")))


def test_unlisted_code_stops(project):
    write_map(project, "survey_code_map.tsv", ("BBBB", "sub-001"))
    with pytest.raises(MissingIdMappingError) as error:
        convert(project)
    assert error.value.missing_ids == ["aaaa"]
    assert written(project) == []


def test_unknown_task_name_warns(project):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    write_map(project, "survey_task-nope_code_map.tsv", ("AAAA", "sub-002"))
    assert "Code map survey_task-nope_code_map.tsv: no template for task 'nope'." in warnings_of(convert(project))


def test_no_maps_behaves_as_before(project):
    result = convert(project, "Code,session,PSS1\nsub-007,pre,0\n")
    assert written(project) == [one_file("sub-007", "ses-1", "pss")]
    assert "code map" not in warnings_of(result).lower()


def test_tracked_map_warns(project):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    git = ["git", "-C", str(project), "-c", "user.name=a", "-c", "user.email=a@b.c"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "code/survey_code_map.tsv"], check=True)
    assert "Code map survey_code_map.tsv is tracked by git; it stays in the history." in warnings_of(convert(project))


def test_a_new_map_is_excluded_from_git(project):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    convert(project)
    ignored = subprocess.run(["git", "-C", str(project), "check-ignore", "code/survey_code_map.tsv"])
    assert ignored.returncode == 0


def test_dry_run_reports_the_same(project):
    write_map(project, "survey_code_map.tsv", ("AAAA", "sub-001"))
    result = convert(project, dry_run=True)
    assert "Applied code map survey_code_map.tsv: 1 code(s)." in warnings_of(result)
    assert written(project) == []
