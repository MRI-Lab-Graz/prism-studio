"""A project path handed to JavaScript must survive it (Windows: ``C:\\Users\\r...\\t...``)."""

import json
import re
from pathlib import Path

import pytest
from jinja2 import Environment

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
ASSIGNMENT = re.compile(r"^\s*window\.currentProject\w+ = (.*\{\{.*\}\}.*);$", re.M)
HOSTILE = 'C:\\Users\\runner\\temp\\new "study" </script>'


@pytest.mark.parametrize(
    "name",
    sorted(p.name for p in TEMPLATES.glob("*.html") if ASSIGNMENT.search(p.read_text(encoding="utf-8"))),
)
def test_current_project_values_reach_javascript_unchanged(name):
    env = Environment(autoescape=True)
    project = {"path": HOSTILE, "name": HOSTILE, "icon": HOSTILE}
    for expression in ASSIGNMENT.findall((TEMPLATES / name).read_text(encoding="utf-8")):
        rendered = env.from_string(expression).render(current_project=project)
        assert "</script" not in rendered
        assert json.loads(rendered) == HOSTILE
