"""A hostile battery for template validation.

Takes a valid template, breaks it in every way a user (or a corrupt file) can, adds entries, and checks that the
validator (1) never crashes, (2) never changes its input, (3) answers the same however the keys are ordered,
(4) flags what is really wrong, and (5) says the same thing in Studio and in the CLI.

Layers checked together as `findings(template)`: the JSON schema, the completeness gate (`gate_findings`: required
fields + declared languages) and the item rules, the same three the Studio Validate button and the save gate run.
"""

from __future__ import annotations

import copy
import importlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parent))
from template_fixtures import library_template, project_template  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from src.prism_template_validation import required_field_paths, validate_template_against_schema  # noqa: E402
from src.survey_template_check import validate_project_templates_for_tasks  # noqa: E402
from src.template_save import gate_findings, gate_schema  # noqa: E402
from src.template_validator import TemplateValidator  # noqa: E402

SECTIONS = ("Technical", "Study", "Metadata", "I18n")
BLANKS = ["", "   ", "\t\n", None, [], {}, {"en": ""}, {"en": "   "}]
HOSTILE_VALUES = [
    None, True, False, 0, -1, 2**63, 1e308, float("inf"), float("nan"), "", " ", "x" * 200_000,
    "‮evil‬", "\x00null", "<script>alert(1)</script>", "../../etc/passwd", "á" * 50,
    "😀" * 100, "'; DROP TABLE x;--", "{{7*7}}", "${jndi:ldap://x}", [], [None], [[]], [[[[[]]]]], {}, {"": ""},
    {"en": None}, {"en": 5}, {"\x00": "x"}, {"a": {"b": {"c": {}}}},
]


def schema() -> dict:
    return gate_schema(project=True)


# Study/TaskName is filled from the file name when absent (with_default_task_name), so it is never "missing"
REQUIRED = [p for p in required_field_paths(gate_schema(project=True)) if p != "Study/TaskName"]


def findings(template, *, project: bool = True) -> list[dict]:
    """Every error the validation layers raise for `template`; must never itself raise."""
    sch = gate_schema(project=project)
    out = [dict(f, layer="schema") for f in validate_template_against_schema(instance=template, schema=sch)]
    if isinstance(template, dict):
        out += [dict(f, layer="gate") for f in gate_findings(template, source="survey-x.json", schema=sch)]
        out += [dict(f, layer="items") for f in TemplateValidator.validate_item_rules_from_data(template)
                if f.get("severity") == "error"]
    return out


def messages(template, **kw) -> set[str]:
    return {f"{f.get('path')}: {f.get('message')}" for f in findings(template, **kw)}


def item_ids(template: dict) -> list[str]:
    return [k for k, v in template.items() if k not in SECTIONS and isinstance(v, dict)]


def base() -> dict:
    return copy.deepcopy(project_template("hostile"))


def set_path(template: dict, path: str, value) -> dict:
    out = copy.deepcopy(template)
    node = out
    *parents, last = path.split("/")
    for part in parents:
        node = node[part]
    node[last] = value
    return out


def drop_path(template: dict, path: str) -> dict:
    out = copy.deepcopy(template)
    node = out
    *parents, last = path.split("/")
    for part in parents:
        node = node[part]
    node.pop(last, None)
    return out


def all_paths(template: dict, depth: int = 3, prefix: str = "") -> list[str]:
    paths = []
    for key, value in template.items():
        path = f"{prefix}{key}"
        paths.append(path)
        if isinstance(value, dict) and depth > 1 and "/" not in str(key):
            paths += all_paths(value, depth - 1, path + "/")
    return paths


# ---------------------------------------------------------------- baseline


def test_the_untouched_template_has_no_errors():
    assert messages(base()) == set()
    assert messages(library_template("hostile"), project=False) == set()


def test_validation_does_not_change_its_input():
    template = base()
    before = json.dumps(template, sort_keys=True)
    findings(template)
    assert json.dumps(template, sort_keys=True) == before


# ---------------------------------------------------------------- 1. take required fields away


@pytest.mark.parametrize("path", REQUIRED)
def test_every_required_field_is_reported_when_removed(path):
    broken = drop_path(base(), path)
    assert any(path in m for m in messages(broken)), f"{path} removed but not reported"


@pytest.mark.parametrize("blank", BLANKS, ids=lambda b: repr(b))
@pytest.mark.parametrize("path", REQUIRED)
def test_every_required_field_is_reported_when_blanked(path, blank):
    broken = set_path(base(), path, blank)
    # "blank" is the one rule everywhere: absent, None, empty/whitespace text, empty list, language object with empty en
    assert any(path in m for m in messages(broken)), f"{path} = {blank!r} accepted"


@pytest.mark.parametrize("section", SECTIONS)
def test_a_missing_section_reports_all_its_required_fields(section):
    broken = base()
    broken.pop(section)
    reported = messages(broken)
    for path in (p for p in REQUIRED if p.startswith(section + "/")):
        assert any(path in m for m in reported), f"{path} not reported when {section} is gone"


@pytest.mark.parametrize("section", SECTIONS)
@pytest.mark.parametrize("junk", [None, [], "text", 5, True, [{"a": 1}]], ids=repr)
def test_a_section_of_the_wrong_type_is_reported_not_a_crash(section, junk):
    assert messages(set_path(base(), section, junk))


# ---------------------------------------------------------------- 2. hostile values in every field


def _value_cases():
    template = base()
    for section in SECTIONS:
        for field in template.get(section, {}):
            for index in range(len(HOSTILE_VALUES)):
                yield f"{section}/{field}", index


@pytest.mark.parametrize("path,index", list(_value_cases()), ids=lambda v: str(v))
def test_no_hostile_value_in_any_field_crashes_validation(path, index):
    broken = set_path(base(), path, copy.deepcopy(HOSTILE_VALUES[index]))
    result = findings(broken)
    assert isinstance(result, list)
    json.dumps(result, default=str)  # the answer itself must be reportable (Studio sends it as JSON)


# ---------------------------------------------------------------- 3. item-level attacks


def first_item(template: dict) -> str:
    return item_ids(template)[0]


def test_min_greater_than_max_is_an_error():
    template = base()
    item = first_item(template)
    template[item]["MinValue"], template[item]["MaxValue"] = 5, 1
    assert any(item in m for m in messages(template))


def test_min_equal_max_is_not_a_crash():
    template = base()
    item = first_item(template)
    template[item]["MinValue"] = template[item]["MaxValue"] = 3
    findings(template)


@pytest.mark.parametrize("value", ["a", None, [], {}, True, float("nan")], ids=repr)
def test_non_numeric_bounds_are_reported_or_ignored_never_crash(value):
    template = base()
    item = first_item(template)
    template[item]["MinValue"] = value
    template[item]["MaxValue"] = value
    findings(template)


@pytest.mark.parametrize("name", list(SECTIONS) + ["", " ", "a b", "a/b", "../x", "x" * 500, "ünï", "0", "-", "__proto__", "constructor"])
def test_hostile_item_ids_never_crash(name):
    template = base()
    template[name] = copy.deepcopy(template[first_item(template)]) if name not in SECTIONS else template.get(name)
    findings(template)


def test_ids_that_differ_only_in_case_are_flagged():
    template = base()
    item = first_item(template)
    template[item.upper() if item.upper() != item else item.lower() + "_"] = copy.deepcopy(template[item])
    twin = item.upper() if item.upper() != item else item.lower() + "_"
    if twin.lower() == item.lower():
        assert any(f.get("layer") == "items" or "case" in f.get("message", "").lower() for f in all_findings_incl_warnings(template))


def all_findings_incl_warnings(template):
    return TemplateValidator.validate_item_rules_from_data(template)


def test_an_item_id_that_is_not_a_safe_column_name_is_warned():
    template = base()
    template["bad id!"] = copy.deepcopy(template[first_item(template)])
    assert any("bad id!" in f["path"] for f in all_findings_incl_warnings(template))


@pytest.mark.parametrize("bad", ["Description", "Levels", "Reversed", "MinValue", "MaxValue"])
def test_item_fields_removed_never_crash(bad):
    template = base()
    for item in item_ids(template):
        template[item].pop(bad, None)
    findings(template)


def test_levels_outside_the_declared_range_are_not_a_crash():
    template = base()
    item = first_item(template)
    template[item]["Levels"] = {"99": {"en": "far outside"}, "-5": {"en": "negative"}, "x": {"en": "text key"}}
    findings(template)


def test_an_item_that_is_not_an_object_is_reported_or_ignored():
    for junk in (None, 5, "text", [], [{"a": 1}]):
        template = base()
        template["stray_item"] = junk
        findings(template)


# ---------------------------------------------------------------- 4. languages


def test_a_declared_language_without_item_texts_is_at_least_a_warning():
    # by design a warning (the declared list is what the editor derives), so look at every severity
    template = base()
    template["I18n"]["Languages"] = ["en", "de", "fr"]  # GAD-7 has en and de only
    found = TemplateValidator.validate_language_consistency_from_data(template, supersede_declared=True)
    assert any("'fr'" in f["message"] for f in found), "declared French but no item has French text"


def test_item_text_in_an_undeclared_language_is_flagged():
    template = base()
    item = first_item(template)
    template[item]["Description"]["fr"] = "bonjour"
    assert any("fr" in m for m in messages(template))


def test_primary_language_not_among_the_declared_ones_is_flagged():
    template = base()
    template["Technical"]["Language"] = "xx"
    assert messages(template)


@pytest.mark.parametrize("code", ["", "EN", "english", "e", "en_US", "en-us-x-whatever-too-long", "12", "\x00", "../", "en\n"])
def test_malformed_language_codes_are_flagged(code):
    template = base()
    item = first_item(template)
    template[item]["Description"][code] = "text"
    assert messages(template), f"language key {code!r} accepted"


def test_session_labels_are_free_strings_never_normalised():
    # CLAUDE.md: "1", "01" and "pre" are three different labels; validation must not coerce them
    template = base()
    template["Study"]["Versions"] = ["1", "01", "pre"]
    assert not any("same" in m.lower() for m in messages(template))


# ---------------------------------------------------------------- 5. new entries (adding, not breaking)


def test_adding_a_valid_item_keeps_the_template_valid():
    template = base()
    new = copy.deepcopy(template[first_item(template)])
    template["added_item_99"] = new
    assert messages(template) == set()


def test_adding_many_items_stays_valid_and_fast():
    template = base()
    proto = template[first_item(template)]
    for i in range(2000):
        template[f"gen_{i:04d}"] = copy.deepcopy(proto)
    assert messages(template) == set()


def test_deeply_nested_garbage_does_not_blow_the_stack():
    deep: object = "x"
    for _ in range(400):
        deep = {"a": deep}
    template = base()
    template["Study"]["Notes"] = deep
    try:
        findings(template)
    except RecursionError:
        pytest.fail("deep nesting crashed validation with RecursionError")


# ---------------------------------------------------------------- 6. whole-document attacks


@pytest.mark.parametrize("junk", [None, [], "text", 5, True, [base()]], ids=lambda v: type(v).__name__)
def test_a_document_that_is_not_an_object_is_never_a_crash(junk):
    assert isinstance(findings(junk), list)


def test_an_empty_template_reports_every_required_field():
    reported = messages({})
    for path in REQUIRED:
        assert any(path in m for m in reported), f"{path} not reported for {{}}"


def test_the_answer_does_not_depend_on_key_order():
    template = base()
    reversed_template = {k: template[k] for k in reversed(list(template))}
    shuffled = dict(random.Random(7).sample(list(template.items()), len(template)))
    assert messages(template) == messages(reversed_template) == messages(shuffled)


def test_the_answer_is_the_same_every_time():
    template = set_path(base(), "Technical/Respondent", "")
    assert messages(template) == messages(template) == messages(copy.deepcopy(template))


# ---------------------------------------------------------------- 7. seeded fuzz


def mutate(template: dict, rng: random.Random) -> dict:
    out = copy.deepcopy(template)
    for _ in range(rng.randint(1, 6)):
        paths = all_paths(out)
        path = rng.choice(paths)
        action = rng.choice(["drop", "replace", "blank", "add", "swap-type"])
        parent_path, _, key = path.rpartition("/")
        node = out
        for part in (parent_path.split("/") if parent_path else []):
            node = node.get(part) if isinstance(node, dict) else None
            if node is None:
                break
        if not isinstance(node, dict):
            continue
        if action == "drop":
            node.pop(key, None)
        elif action == "replace":
            node[key] = copy.deepcopy(rng.choice(HOSTILE_VALUES))
        elif action == "blank":
            node[key] = rng.choice(BLANKS)
        elif action == "add":
            node[f"Fuzz{rng.randint(0, 999)}"] = copy.deepcopy(rng.choice(HOSTILE_VALUES))
        else:
            node[key] = [node.get(key)] if rng.random() < 0.5 else {"en": node.get(key)}
    return out


@pytest.mark.parametrize("seed", range(300))
def test_fuzz_no_mutation_crashes_or_changes_its_input_or_answers_unstably(seed):
    rng = random.Random(seed)
    mutated = mutate(base(), rng)
    snapshot = json.dumps(mutated, sort_keys=True, default=str)
    first = messages(mutated)
    assert json.dumps(mutated, sort_keys=True, default=str) == snapshot, "validation changed its input"
    assert messages(copy.deepcopy(mutated)) == first, "same template, different answer"


@pytest.mark.parametrize("seed", range(100))
def test_fuzz_a_template_that_dropped_a_required_field_is_never_called_valid(seed):
    rng = random.Random(10_000 + seed)
    path = rng.choice(REQUIRED)
    mutated = mutate(drop_path(base(), path), rng)
    section, field = path.split("/")
    # the mutation may have put a value back; only judge when the field is still absent or blank
    value = (mutated.get(section) or {}).get(field) if isinstance(mutated.get(section), dict) else None
    if value in (None, "", [], {}):
        assert any(path in m for m in messages(mutated)), f"{path} gone but template accepted"


# ---------------------------------------------------------------- 8. Studio and CLI say the same


def _studio_client():
    handlers = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(ROOT / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(handlers.tools_template_editor_bp)
    return app.test_client()


@pytest.mark.parametrize("junk", [None, [], "x", 5], ids=repr)
def test_studio_validate_refuses_a_non_object_with_400_not_500(junk):
    response = _studio_client().post("/api/template-editor/validate", json={"modality": "survey", "template": junk})
    assert response.status_code == 400


@pytest.mark.parametrize("seed", range(25))
def test_studio_validate_never_answers_500(seed):
    mutated = mutate(base(), random.Random(20_000 + seed))
    try:
        body = json.dumps({"modality": "survey", "schema_version": "stable", "template": mutated}, allow_nan=False, default=str)
    except ValueError:
        pytest.skip("not representable as JSON (a browser could not send it either)")
    response = _studio_client().post("/api/template-editor/validate", data=body, content_type="application/json")
    assert response.status_code == 200, response.get_data(as_text=True)[:300]


def test_cli_and_studio_agree_on_which_templates_are_incomplete(tmp_path):
    cases = {}
    for i, path in enumerate(REQUIRED):
        cases[f"m{i}"] = drop_path(base(), path)
    cases["ok"] = base()
    folder = tmp_path / "code" / "library" / "survey"
    folder.mkdir(parents=True)
    for task, template in cases.items():
        (folder / f"survey-{task}.json").write_text(json.dumps(template), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "app" / "prism_tools.py"), "library", "template-check", "--project", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), timeout=300,
    )
    for task, template in cases.items():
        studio = validate_project_templates_for_tasks(tasks=[task], project_path=str(tmp_path))
        incomplete = bool(studio)
        assert (f"survey-{task}.json" in result.stdout) == incomplete, f"{task}: CLI and Studio disagree\n{result.stdout}"
    assert result.returncode == 1
