"""Real, valid templates for tests that save through the shared save function (no stubbed validation)."""

import json
from pathlib import Path

GAD7 = Path(__file__).resolve().parents[1] / "official" / "library" / "survey" / "survey-gad7.json"


def library_template(task: str = "gad7") -> dict:
    """A library template: the official GAD-7 with a task name (the library relaxation never waives that)."""
    template = json.loads(GAD7.read_text(encoding="utf-8"))
    template["Study"]["TaskName"] = task
    return template


def project_template(task: str = "gad7") -> dict:
    """A project copy: a library template that also says how it was administered."""
    template = library_template(task)
    template["Technical"].update(SoftwarePlatform="Other", SoftwareVersion="1", AdministrationMethod="paper")
    return template
