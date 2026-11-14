"""Real, valid templates for tests that save through the shared save function (no stubbed validation)."""

import functools
import json
import tempfile
from pathlib import Path

OFFICIAL_SURVEYS = Path(__file__).resolve().parents[1] / "official" / "library" / "survey"
DEMO = OFFICIAL_SURVEYS / "survey-demo.json"
# The templates Studio ships itself; tests never depend on any other file of the official library.
SHIPPED = ("survey-dass.json", "survey-dass21.json", "survey-demo.json")


def library_template(task: str = "demo") -> dict:
    """A library template: the official demo questionnaire (8 items DEMO01-08, scale 0-4) with a task name (the library relaxation never waives that)."""
    template = json.loads(DEMO.read_text(encoding="utf-8"))
    template["Study"]["TaskName"] = task
    return template


_RESERVED = {"Technical", "Study", "Metadata", "I18n"}


def complete(template: dict, task: str = "x") -> dict:
    """``template`` with every field a project template must have (what it already says is kept), so a converter
    or exporter test can use a small hand-written template. Declared languages are the ones its items use."""
    out = json.loads(json.dumps(template))

    def fill(section: str, defaults: dict) -> None:
        values = out.setdefault(section, {})
        for key, value in defaults.items():
            if values.get(key) in (None, "", [], {}):
                values[key] = value

    languages = sorted({
        code for key, item in out.items() if key not in _RESERVED and isinstance(item, dict)
        for code in (item.get("Description") if isinstance(item.get("Description"), dict) else {})
    }) or ["en"]
    fill("Technical", {"StimulusType": "Questionnaire", "FileFormat": "tsv", "SoftwarePlatform": "Other", "SoftwareVersion": "1",
                       "Language": languages[0], "Respondent": "self", "AdministrationMethod": "online"})
    fill("Study", {"TaskName": task, "OriginalName": {"en": task}, "Citation": "Test, T. (2026).", "LicenseID": "CC0-1.0"})
    fill("Metadata", {"SchemaVersion": "2.0.0", "CreationDate": "2026-01-01", "Creator": "tests"})
    fill("I18n", {"Languages": languages})
    return out


@functools.cache
def completed_official_library() -> Path:
    """A copy of the shipped survey templates (dass, dass21, demo) whose templates are complete project copies: converting data needs
    that, and the official files (which leave Respondent, AdministrationMethod, SoftwarePlatform to the project)
    are never converted from directly."""
    folder = Path(tempfile.mkdtemp(prefix="prism-official-complete-"))
    for name in SHIPPED:
        template = json.loads((OFFICIAL_SURVEYS / name).read_text(encoding="utf-8"))
        (folder / name).write_text(json.dumps(complete(template, name[len("survey-"):-len(".json")])), encoding="utf-8")
    return folder


def bilingual(template: dict) -> dict:
    """``template`` with every item text in English and German (the demo template is English only), for tests that
    need a declared second language."""
    out = json.loads(json.dumps(template))
    for key, item in out.items():
        if key not in _RESERVED and isinstance(item, dict) and isinstance(item.get("Description"), str):
            item["Description"] = {"en": item["Description"], "de": f"[de] {item['Description']}"}
    out.setdefault("I18n", {})["Languages"] = ["en", "de"]
    return out


def dump_complete(template: dict, task: str | None = None) -> str:
    """``json.dumps(complete(template))``; the task name is the template's own unless given."""
    return json.dumps(complete(template, task or (template.get("Study") or {}).get("TaskName") or "x"))


def project_template(task: str = "demo") -> dict:
    """A project copy: a library template that also says how it was administered."""
    template = library_template(task)
    template["Technical"].update(SoftwarePlatform="Other", SoftwareVersion="1", AdministrationMethod="paper", Respondent="self")
    return template
