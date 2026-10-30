"""Studio and `library template-check` run one function, so a legacy paper template is read the same in both."""

import json

from src.survey_template_check import validate_project_templates_for_tasks
from tests.template_fixtures import project_template


def test_a_paper_template_without_software_platform_is_complete_without_the_caller_normalizing_it(tmp_path):
    template = project_template()
    template["Technical"]["AdministrationMethod"] = "paper"
    template["Technical"].pop("SoftwarePlatform")
    folder = tmp_path / "code" / "library" / "survey"
    folder.mkdir(parents=True)
    (folder / "survey-x.json").write_text(json.dumps(template), encoding="utf-8")

    assert validate_project_templates_for_tasks(tasks=["x"], project_path=str(tmp_path)) == []
