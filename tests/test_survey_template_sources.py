"""A survey template comes from the project, else the personal library, else the global one."""

import json
from pathlib import Path

from src.config import AppSettings
from src.survey_template_sources import build_effective_library, copy_used_templates_to_project, template_tiers


def _put(folder: Path, task: str, origin: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    template = {"Study": {"TaskName": task}, "Metadata": {"Creator": origin}, "Q1": {"Levels": {"0": "a", "1": "b"}}}
    (folder / f"survey-{task}.json").write_text(json.dumps(template), encoding="utf-8")


def _world(tmp_path):
    """project has a+b, personal has b+c, global has c+d."""
    project, mine, shared = tmp_path / "proj", tmp_path / "mine", tmp_path / "shared"
    for task in ("a", "b"):
        _put(project / "code" / "library" / "survey", task, "project")
    for task in ("b", "c"):
        _put(mine / "library" / "survey", task, "personal")
    for task in ("c", "d"):
        _put(shared / "library" / "survey", task, "global")
    settings = AppSettings(personal_library_path=str(mine), global_library_root=str(shared))
    return project, settings


def _creator(library, task):
    return json.loads((library.directory / f"survey-{task}.json").read_text(encoding="utf-8"))["Metadata"]["Creator"]


def test_tiers_are_project_then_personal_then_global(tmp_path):
    project, settings = _world(tmp_path)
    labels = [t.label for t in template_tiers(project, tmp_path / "app", settings)]
    assert labels == ["project", "personal", "global"]


def test_each_task_comes_from_the_nearest_library_that_has_it(tmp_path):
    project, settings = _world(tmp_path)
    library = build_effective_library(project, tmp_path / "app", settings)
    assert {t: _creator(library, t) for t in "abcd"} == {
        "a": "project", "b": "project", "c": "personal", "d": "global",
    }
    assert {t: tier.label for t, tier in library.origins.items()} == {
        "a": "project", "b": "project", "c": "personal", "d": "global",
    }


def test_without_a_personal_library_it_is_project_then_global(tmp_path):
    project, settings = _world(tmp_path)
    settings.personal_library_path = None
    library = build_effective_library(project, tmp_path / "app", settings)
    assert _creator(library, "c") == "global"


def test_no_library_anywhere_gives_an_empty_library(tmp_path):
    library = build_effective_library(None, tmp_path / "app", AppSettings())
    assert library.origins == {}


def test_used_templates_from_other_libraries_are_copied_into_the_project(tmp_path):
    project, settings = _world(tmp_path)
    library = build_effective_library(project, tmp_path / "app", settings)
    summary = copy_used_templates_to_project(library, ["b", "c", "d"], project, technical_defaults={"SoftwarePlatform": "LimeSurvey"})

    mine = project / "code" / "library" / "survey"
    assert summary["existing_tasks"] == ["b"]  # the project's own template is never overwritten
    assert summary["copied_tasks"] == ["c", "d"]
    copied = json.loads((mine / "survey-c.json").read_text(encoding="utf-8"))
    assert copied["Metadata"]["Creator"] == "personal"
    assert copied["Technical"]["SoftwarePlatform"] == "LimeSurvey"  # prepared like an official copy
    assert json.loads((mine / "survey-b.json").read_text(encoding="utf-8"))["Metadata"]["Creator"] == "project"


def test_only_the_standard_libraries_are_merged_an_explicit_folder_is_used_as_given(tmp_path):
    from src.survey_template_sources import is_standard_library

    project, settings = _world(tmp_path)
    app = tmp_path / "app"
    assert is_standard_library(project / "code" / "library" / "survey", project, app, settings)
    assert is_standard_library(project / "code" / "library", project, app, settings)
    assert is_standard_library(tmp_path / "mine" / "library" / "survey", project, app, settings)
    assert is_standard_library(tmp_path / "shared" / "library" / "survey", project, app, settings)
    assert not is_standard_library(tmp_path / "somewhere" / "else", project, app, settings)
    # a project that has no templates yet still counts: its code/library is where they are put
    empty = tmp_path / "new"
    assert is_standard_library(empty / "code" / "library" / "survey", empty, app, settings)
