"""`survey item-map`: guess, accept or set the column-to-item map of a task in a project."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.cli.commands.survey import cmd_survey_item_map  # noqa: E402
from tests.template_fixtures import dump_complete  # noqa: E402

ITEMS = ["ADS01", "ADS02"]
TEMPLATE = {i: {"Description": {"en": i}, "Levels": {"1": "low", "2": "high"}} for i in ITEMS}


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    library = root / "code" / "library" / "survey"
    library.mkdir(parents=True)
    (library / "survey-ads.json").write_text(dump_complete(TEMPLATE, "ads"), encoding="utf-8")
    (tmp_path / "in.csv").write_text("participant_id,A01,A02\nsub-001,1,2\n", encoding="utf-8")
    return root


def run(project, **kw):
    args = dict(input=str(project.parent / "in.csv"), project=str(project), task=None, accept=False, set=None)
    cmd_survey_item_map(SimpleNamespace(**{**args, **kw}))


def saved(project):
    return json.loads((project / "code" / "item_maps" / "ads.json").read_text(encoding="utf-8"))


def test_without_task_it_lists_the_tasks_that_need_a_map(project, capsys):
    run(project)
    assert "ads" in capsys.readouterr().out
    assert not (project / "code" / "item_maps").exists()


def test_with_task_it_prints_the_guess_and_writes_nothing(project, capsys):
    run(project, task="ads")
    assert "ADS01 <- A01  (number)" in capsys.readouterr().out
    assert not (project / "code" / "item_maps").exists()


def test_accept_saves_the_guess(project):
    run(project, task="ads", accept=True)
    assert saved(project) == {"ADS01": "A01", "ADS02": "A02"}


def test_set_overrides_one_row_of_the_accepted_guess(project):
    run(project, task="ads", accept=True, set=["ADS02=A01", "ADS01=A02"])
    assert saved(project) == {"ADS01": "A02", "ADS02": "A01"}


def test_set_alone_saves_only_what_was_set(project):
    run(project, task="ads", set=["ADS01=A01"])
    assert saved(project) == {"ADS01": "A01"}


def test_a_column_not_in_the_file_is_refused(project):
    with pytest.raises(SystemExit):
        run(project, task="ads", set=["ADS01=NOPE"])
    assert not (project / "code" / "item_maps").exists()


def test_an_unknown_task_is_refused(project):
    with pytest.raises(SystemExit):
        run(project, task="nope")
