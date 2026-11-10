"""The survey templates handed out with the examples must pass the converter's own pre-conversion check."""
import shutil
from pathlib import Path

import pytest

from src.survey_template_check import validate_project_templates_for_tasks

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
HANDED_OUT = [
    "workshop/chapter_3_survey_import/survey-wellbeing.json",
    "excel_template/basic/survey-mood.json",
    "excel_template/advanced/survey-wellcheck.json",
]


@pytest.mark.parametrize("rel", HANDED_OUT)
def test_handed_out_template_is_complete(rel, tmp_path):
    folder = tmp_path / "code" / "library" / "survey"
    folder.mkdir(parents=True)
    shutil.copy(EXAMPLES / rel, folder)

    assert validate_project_templates_for_tasks(tasks=None, project_path=str(tmp_path)) == []
