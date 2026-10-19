"""The tools are blocked on a project without Name, Authors, Keywords and Timepoints, so every
project that ships with PRISM (the tutorials point at them) must have them."""

from pathlib import Path

import pytest

from src.project_ready import missing_required_fields

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = sorted({p.parent for p in ROOT.joinpath("examples").rglob("project.json")})


@pytest.mark.parametrize("project", SHIPPED, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_a_shipped_project_is_not_blocked_by_the_required_fields_gate(project):
    assert missing_required_fields(project) == []
