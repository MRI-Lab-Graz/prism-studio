"""A conversion refused for an incomplete template leaves the project copy to fix, and names it."""

import json
from pathlib import Path

import pytest

from src.survey_template_sources import run_survey_with_template_sources
from src.template_save import TemplateIncomplete

APP = Path(__file__).resolve().parents[1] / "app"


def test_a_refused_conversion_leaves_the_incomplete_template_in_the_project_to_fix(tmp_path):
    """The user cannot fix a library file; the refusal puts the template where the Template editor finds it
    (the project's code/library) and names that copy, so the next step is to fill it in."""
    library = tmp_path / "lib" / "survey"
    library.mkdir(parents=True)
    (library / "survey-x.json").write_text(json.dumps({"Study": {"TaskName": "x"}}), encoding="utf-8")
    project = tmp_path / "proj"
    (project / "code" / "library" / "survey").mkdir(parents=True)
    (project / "project.json").write_text("{}", encoding="utf-8")

    temp_source = str(tmp_path / "merged" / "survey-x.json")  # where the converter found it: not the user's file

    def refuse(**_):
        raise TemplateIncomplete(
            [{"path": "Technical/Respondent", "message": f"Technical/Respondent is missing in {temp_source}",
              "task": "x", "source": temp_source}],
            tasks=["x"],
        )

    with pytest.raises(TemplateIncomplete) as refused:
        run_survey_with_template_sources(
            refuse, library_dir=tmp_path / "lib", fallback_project_path=str(project), app_root=APP
        )

    copy = project / "code" / "library" / "survey" / "survey-x.json"
    assert copy.is_file()
    assert f"Technical/Respondent is missing in {copy}" in str(refused.value)  # the field line names the copy
    assert temp_source not in str(refused.value)
