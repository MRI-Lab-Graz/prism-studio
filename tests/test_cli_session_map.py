"""prism_tools.py session-map show / set, and conversion failing with the label list."""

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.session_map import cmd_session_map_set, cmd_session_map_show  # noqa: E402
from src.cli.commands.survey import cmd_survey_convert  # noqa: E402
from src.session_map import load_session_map  # noqa: E402

BRS = Path(__file__).resolve().parents[1] / "official" / "library" / "survey" / "survey-brs.json"


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "multiple"}}))
    return root


def test_set_then_show_lists_only_what_the_user_entered(proj, capsys):
    cmd_session_map_set(SimpleNamespace(project=str(proj), label="pre", target="1"))
    cmd_session_map_set(SimpleNamespace(project=str(proj), label="T0", target="1"))
    assert load_session_map(proj) == {"pre": "1", "T0": "1"}

    capsys.readouterr()
    cmd_session_map_show(SimpleNamespace(project=str(proj), json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"timepoints": "multiple", "map": {"pre": "1", "T0": "1"}}


def test_set_rejects_an_invalid_target_with_exit_code_2(proj, capsys):
    with pytest.raises(SystemExit) as info:
        cmd_session_map_set(SimpleNamespace(project=str(proj), label="pre", target="ses-1"))
    assert info.value.code == 2
    assert "letters and digits" in capsys.readouterr().out
    assert load_session_map(proj) == {}


def survey_args(tmp_path, proj, csv_text, **overrides):
    lib = tmp_path / "lib"
    lib.mkdir(exist_ok=True)
    shutil.copy(BRS, lib / "survey-brs.json")
    data = tmp_path / "in.csv"
    data.write_text(csv_text)
    values = dict(
        input=str(data), output=str(tmp_path / "out"), library=str(lib), project=str(proj),
        survey=None, id_column="participant_id", session_column="session", sheet=0,
        unknown="warn", dry_run=False, force=False, name="t", authors=None, lang="en",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def error_line(capsys):
    out = capsys.readouterr().out
    return next(line for line in out.splitlines() if line.startswith("Error:"))


TWO = "participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP001,post,4,4,3\n"


def test_survey_convert_fails_naming_the_unmapped_labels(tmp_path, proj, capsys):
    with pytest.raises(SystemExit) as info:
        cmd_survey_convert(survey_args(tmp_path, proj, TWO))
    assert info.value.code == 1
    error = error_line(capsys)  # the Error: line itself, not the INFO chatter above it
    assert "'pre'" in error and "'post'" in error and "session-map set" in error


def test_survey_convert_never_silently_drops_a_session(tmp_path, proj, capsys):
    cmd_session_map_set(SimpleNamespace(project=str(proj), label="post", target="2"))
    with pytest.raises(SystemExit) as info:
        cmd_survey_convert(survey_args(tmp_path, proj, TWO))
    assert info.value.code == 1
    error = error_line(capsys)
    assert "'pre'" in error and "'post'" not in error  # 'pre' is what is missing


def test_set_then_convert_succeeds_and_writes_the_mapped_sessions(tmp_path, proj):
    cmd_session_map_set(SimpleNamespace(project=str(proj), label="pre", target="1"))
    cmd_session_map_set(SimpleNamespace(project=str(proj), label="post", target="2"))
    cmd_survey_convert(survey_args(tmp_path, proj, TWO))
    assert sorted(p.name for p in (tmp_path / "out" / "sub-P001").glob("ses-*")) == ["ses-1", "ses-2"]


def test_session_flag_chooses_the_session_for_a_file_without_a_session_column(tmp_path, proj):
    cmd_session_map_set(SimpleNamespace(project=str(proj), label="pre", target="1"))
    csv_text = "participant_id,BRS01,BRS02,BRS03\nP001,3,4,2\n"
    cmd_survey_convert(survey_args(tmp_path, proj, csv_text, session_column=None, session="pre"))
    assert sorted(p.name for p in (tmp_path / "out" / "sub-P001").glob("ses-*")) == ["ses-1"]


def test_output_folder_that_is_a_longitudinal_project_applies_its_rule_without_the_project_flag(
    tmp_path, proj, capsys
):
    args = survey_args(tmp_path, proj, TWO, project=None, output=str(proj), force=True)
    with pytest.raises(SystemExit) as info:
        cmd_survey_convert(args)
    assert info.value.code == 1
    assert "session-map set" in error_line(capsys)
    assert not list(proj.glob("sub-*"))  # nothing was written into the project
