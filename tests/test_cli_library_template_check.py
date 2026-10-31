"""`library template-check` is Studio's pre-conversion template check as a command: the same function runs both."""

import json
import subprocess
import sys
from pathlib import Path

from src.survey_template_check import validate_project_templates_for_tasks
from tests.template_fixtures import project_template

ROOT = Path(__file__).resolve().parent.parent


def _project(tmp_path, **templates):
    folder = tmp_path / "code" / "library" / "survey"
    folder.mkdir(parents=True)
    for task, template in templates.items():
        (folder / f"survey-{task}.json").write_text(json.dumps(template), encoding="utf-8")
    return tmp_path


def _check(project, *extra):
    return subprocess.run(
        [sys.executable, str(ROOT / "app" / "prism_tools.py"), "library", "template-check", "--project", str(project), *extra],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), timeout=120,
    )


def test_a_complete_project_exits_zero(tmp_path):
    result = _check(_project(tmp_path, x=project_template()))

    assert result.returncode == 0, result.stdout + result.stderr


def test_an_incomplete_template_is_listed_and_exits_one(tmp_path):
    incomplete = project_template()
    incomplete["Technical"].pop("Respondent")
    project = _project(tmp_path, x=incomplete)

    result = _check(project)

    assert result.returncode == 1
    assert "Technical/Respondent is missing" in result.stdout


def test_the_command_lists_exactly_what_studio_reports(tmp_path):
    incomplete = project_template()
    incomplete["Technical"].pop("Respondent")
    incomplete["Metadata"].pop("Creator")
    project = _project(tmp_path, x=incomplete, y=project_template())

    studio = [i["message"] for i in validate_project_templates_for_tasks(tasks=["x", "y"], project_path=str(project))]
    cli = _check(project, "--tasks", "x,y").stdout

    assert studio and all(message in cli for message in studio)


def test_without_tasks_every_survey_template_of_the_project_is_checked(tmp_path):
    incomplete = project_template()
    incomplete["Technical"].pop("Respondent")

    result = _check(_project(tmp_path, a=project_template(), b=incomplete))

    issues = "\n".join(line for line in result.stdout.splitlines() if not line.startswith("Warning:"))  # warnings never block
    assert result.returncode == 1
    assert "survey-b.json" in issues
    assert "survey-a.json" not in issues
