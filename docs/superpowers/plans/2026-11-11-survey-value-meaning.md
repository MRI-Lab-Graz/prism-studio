# Step 3: what a value means (survey) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A survey says in its own files how long ago an answer refers to (`RecallPeriod`) and what a high score means (`HigherMeans`, `LowerMeans`), and Studio shows both.

**Architecture:** Two optional text fields in two places. `Study.RecallPeriod` (and an item-level override) goes into the vendored `survey.schema.json`, so it is a prism-specification patch release (v1.5.5) followed by a sync. `HigherMeans` / `LowerMeans` go on a recipe score in `recipe.survey.schema.json`, which Studio owns, so no release. The derived survey registry (`src/survey_terms.py`) copies them onto the instrument, item and score terms, so `terms show` prints them with no new command.

**Tech Stack:** JSON Schema draft 7, Python 3 (pytest), prism-specification scripts (`check_schema_versions.py`, `generate_schema_reference.py`), `scripts/sync_specification.py` in Studio.

**Spec:** `docs/superpowers/specs/2026-11-11-term-ids-all-modalities-design.md` (section "Step 3: what a value means", answers 6 and 8). Text now; the direction a program can read goes on the link in step 4, not here.

## Global Constraints

- Both repos: TDD. A failing test first, watched failing; no test written after the fix.
- Specification releases bump the PATCH version: the tag is `v1.5.5`, not 1.6.0. Small steps; merge and tag only after the user confirms. `ponytail:ponytail-audit` runs before every merge to `main` in either repo.
- prism-specification: a changed stable schema carries a bumped `version` and `$id`; the previous version is archived unchanged under `schemas/archive/survey/`; the spec page tables are regenerated (`python scripts/generate_schema_reference.py`). `python scripts/check_schema_versions.py <base> <head>` must pass.
- The vendored copy in Studio is never edited by hand: `python scripts/sync_specification.py --tag v1.5.5`, then pin the new tag in `tests/test_vendored_specification.py`.
- THE RULE: no new CLI command is needed (`terms show` already prints a whole term); Studio JavaScript only lists a field.
- Project and library files are untrusted data: a wrong type is reported or ignored, never a crash.
- An empty string is never a value (the survey schema's existing rule); a text object needs a non-empty `en` (the English rule).
- No content curation here: the fields are optional and no official template or recipe is filled in this step.
- Field names (decided here, user agreed to the content): `Study.RecallPeriod`, item `RecallPeriod`, score `HigherMeans`, score `LowerMeans`.

## Review Focus

1. A template or recipe without any of the new fields: validates and prints exactly as before (Tasks 1, 3, 4).
2. An empty string, a number or an object without `en` as a `RecallPeriod`: refused by the schema (Task 1).
3. A recipe whose `HigherMeans` is a number or a list (project data): the registry ignores it and reports nothing worse than before; no crash (Task 4).
4. `LowerMeans` given without `HigherMeans`: allowed; it is optional text on its own (Task 3).
5. The released stable schema differs from the archived one only by the new fields, version and `$id` (Task 1; the version check script).

## File Structure

prism-specification (branch `feat/recall-period`):
- Modify `schemas/stable/survey.schema.json`: `Study.RecallPeriod`, item `RecallPeriod`, `version` 2.0.0 to 2.1.0, `$id` suffix.
- Create `schemas/archive/survey/2.0.0.schema.json`: byte copy of the current stable file.
- Modify `specs/survey.md`: regenerated tables, one sentence on the field.
- Modify `tests/test_survey_schema.py`.

prism-studio (branch `feat/survey-value-meaning`, worktree from `main`):
- Sync output: `app/schemas/**/survey*`, `docs/specs/survey.md`, `specification.lock.json`; `tests/test_vendored_specification.py` (pin).
- Modify `app/schemas/stable/recipe.survey.schema.json`: `HigherMeans`, `LowerMeans`.
- Modify `src/survey_terms.py`: copy the fields onto the registry terms.
- Modify `app/static/js/template-editor/questionnaire-sections.js`: list `Study/RecallPeriod`.
- Modify `docs/CLI_REFERENCE.md` (what `terms show --modality survey` prints) and the recipe documentation page that lists `Interpretation`.
- Tests: `tests/test_recipe_value_meaning.py` (new), `tests/test_survey_terms.py`.

---

### Task 1: `RecallPeriod` in the survey schema (prism-specification)

**Files:**
- Modify: `schemas/stable/survey.schema.json`, `specs/survey.md`
- Create: `schemas/archive/survey/2.0.0.schema.json`
- Test: `tests/test_survey_schema.py`

**Interfaces:**
- Produces: `Study.RecallPeriod` and item `RecallPeriod`, each `string` (non-empty) or an object with a non-empty `en`; stable survey schema `version` `2.1.0`.

- [ ] **Step 1: Write the failing tests** in `tests/test_survey_schema.py`, using its `BASE` document and `V` validator:

```python
def _with_period(value):
    doc = copy.deepcopy(BASE)
    doc["Study"]["RecallPeriod"] = value
    return doc

@pytest.mark.parametrize("value", ["past 2 weeks", "P14D", {"en": "past 2 weeks", "de": "letzte 2 Wochen"}])
def test_study_recall_period_accepts_text_and_english_object(value):
    assert not list(V.iter_errors(_with_period(value)))

@pytest.mark.parametrize("value", ["", 14, ["past 2 weeks"], {"de": "letzte 2 Wochen"}, {"en": ""}])
def test_study_recall_period_refuses_empty_wrong_type_or_no_english(value):
    assert list(V.iter_errors(_with_period(value)))

def test_an_item_may_set_its_own_recall_period_and_the_schema_refuses_an_empty_one():
    doc = copy.deepcopy(BASE)
    doc["Q01"] = {"Description": {"en": "Today I felt tired"}, "RecallPeriod": "today"}
    assert not list(V.iter_errors(doc))
    doc["Q01"]["RecallPeriod"] = ""
    assert list(V.iter_errors(doc))

def test_a_template_without_recall_period_still_validates():
    assert not list(V.iter_errors(copy.deepcopy(BASE)))

def test_the_previous_survey_schema_is_archived_unchanged_and_the_version_is_bumped():
    stable = json.loads((ROOT / "schemas/stable/survey.schema.json").read_text())
    assert stable["version"] == "2.1.0" and stable["$id"].endswith("/v2.1.0")
    old = json.loads((ROOT / "schemas/archive/survey/2.0.0.schema.json").read_text())
    assert old["version"] == "2.0.0"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_survey_schema.py -q`
Expected: the recall-period and version tests FAIL (the item and `Study` accept any `RecallPeriod` today because the item object is open, so the refusal cases fail; the version test fails on `2.0.0`).

- [ ] **Step 3: Release the schema** per `CONTRIBUTING.md`: copy the current stable file unchanged to `schemas/archive/survey/2.0.0.schema.json`; in the stable file bump `version` to `2.1.0` and the `$id` suffix to `v2.1.0`; add `Study.RecallPeriod` and the item `RecallPeriod` as `{"type": ["string", "object"], "minLength": 1, "properties": {"en": {"type": "string", "minLength": 1}}, "required": ["en"]}` (the `required` applies to the object form only; mirror how `Study.Instructions` states the English rule and copy that pattern exactly if it differs), with a description such as "The period an answer refers to, for example 'past 2 weeks' or an ISO 8601 duration ('P14D'). An item may set its own."; edit only these lines, keep the file's formatting. Then `python scripts/generate_schema_reference.py` and add one sentence on the field to `specs/survey.md` under the `Study` section.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests -q && python scripts/generate_schema_reference.py --check && python scripts/check_schema_versions.py origin/main HEAD`
Expected: all PASS; the version check prints no error.

- [ ] **Step 5: Commit** on branch `feat/recall-period`

```bash
git add schemas specs tests
git commit -m "feat(survey): Study.RecallPeriod and an item-level RecallPeriod; survey schema 2.1.0 (2.0.0 archived)"
```

### Task 2: Release v1.5.5 and sync it into Studio

**Files:** (prism-specification) none new; (prism-studio) `app/schemas/**`, `docs/specs/survey.md`, `specification.lock.json`, `tests/test_vendored_specification.py`.

**Interfaces:**
- Consumes: Task 1's merged schema.
- Produces: tag `v1.5.5`; Studio's vendored `survey.schema.json` with `RecallPeriod`.

- [ ] **Step 1: Ask the user to confirm** the merge of the specification PR and the tag `v1.5.5` (the ponytail audit runs first). Do nothing irreversible before the answer.
- [ ] **Step 2: Merge, tag, push the tag** in prism-specification once confirmed.
- [ ] **Step 3: Write the failing pin test.** In `tests/test_vendored_specification.py` change the expected tag `v1.5.4` to `v1.5.5`. Run `python -m pytest tests/test_vendored_specification.py -q`. Expected: FAIL (lock still v1.5.4).
- [ ] **Step 4: Sync.** In the Studio worktree on a new branch `feat/survey-value-meaning`: `python scripts/sync_specification.py --tag v1.5.5`.
- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/test_vendored_specification.py tests/test_survey_schema*.py -q` (use the existing survey schema test files by `ls tests | grep -i survey_schema`)
Expected: PASS.

- [ ] **Step 6: Commit** `chore(specification): sync prism-specification v1.5.5 (Study.RecallPeriod)`.

### Task 3: `HigherMeans` and `LowerMeans` in the recipe schema (Studio)

**Files:**
- Modify: `app/schemas/stable/recipe.survey.schema.json` (the `Scores` items properties, next to `Interpretation`)
- Test: `tests/test_recipe_value_meaning.py` (new)

**Interfaces:**
- Produces: score properties `HigherMeans`, `LowerMeans`: `string`, `minLength` 1, optional, independent of each other.

- [ ] **Step 1: Write the failing tests**

```python
import copy, json
from pathlib import Path
import pytest
from jsonschema import Draft7Validator

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "app/schemas/stable/recipe.survey.schema.json").read_text())
V = Draft7Validator(SCHEMA)

def _recipe(**score_extra):
    # start from the smallest valid recipe: copy one official recipe and keep one score
    path = next((Path(__file__).resolve().parents[1] / "official/recipe/survey").glob("recipe-phq9.json"))
    recipe = json.loads(path.read_text())
    recipe["Scores"] = [{**recipe["Scores"][0], **score_extra}]
    return recipe

def test_higher_and_lower_means_are_accepted():
    assert not list(V.iter_errors(_recipe(HigherMeans="more depressive symptoms", LowerMeans="fewer depressive symptoms")))

def test_lower_means_alone_is_accepted():
    assert not list(V.iter_errors(_recipe(LowerMeans="more introverted")))

@pytest.mark.parametrize("value", ["", 3, ["more"], None])
def test_higher_means_refuses_empty_or_non_text(value):
    assert list(V.iter_errors(_recipe(HigherMeans=value)))

def test_a_recipe_without_them_still_validates():
    assert not list(V.iter_errors(_recipe()))
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_recipe_value_meaning.py -q`
Expected: only the "refuses" cases FAIL (the schema accepts unknown score keys today); the accept cases pass already, which is fine: they pin that nothing breaks.

- [ ] **Step 3: Add the two properties** to `Scores.items.properties`: `"HigherMeans": {"type": "string", "minLength": 1, "description": "What a higher score means, in a few words (for example 'more depressive symptoms')."}` and `"LowerMeans"` likewise ("what a lower score means; only for two-sided scales, where it is not just the negation"). Do not add them to `required`. Do not bump the schema `version` unless a Studio test pins it (then bump the minor).
- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_recipe_value_meaning.py tests -k "recipe" -q`
Expected: PASS.

- [ ] **Step 5: Commit** `feat(recipe): HigherMeans and LowerMeans on a score`.

### Task 4: The survey registry carries them

**Files:**
- Modify: `src/survey_terms.py` (`build_survey_registry`)
- Test: `tests/test_survey_terms.py`

**Interfaces:**
- Consumes: `build_survey_registry(library_dir, recipe_dir)`, `_text(value) -> str` (existing).
- Produces: the instrument term gets `RecallPeriod` (from `Study.RecallPeriod`, text via `_text`), an item term gets `RecallPeriod` only if the item sets its own, a score term gets `HigherMeans` / `LowerMeans`. A missing, empty or non-text value is left out; nothing else about the registry changes.

- [ ] **Step 1: Write the failing tests** in `tests/test_survey_terms.py`, using its existing `_lib` helper that writes a library and recipe folder (read it first and reuse it; add `Study.RecallPeriod` and a score with `HigherMeans` to what it writes in the test body):

```python
def test_recall_period_and_direction_reach_the_terms(tmp_path):
    lib, rec = _lib(tmp_path, study_extra={"RecallPeriod": {"en": "past 2 weeks"}},
                    item_extra={"Q02": {"Description": {"en": "Today I felt tired"}, "RecallPeriod": "today"}},
                    score_extra={"HigherMeans": "more symptoms", "LowerMeans": "fewer symptoms"})
    registry, problems = build_survey_registry(lib, rec)
    assert registry["x"]["RecallPeriod"] == "past 2 weeks"
    assert registry["x.q02"]["RecallPeriod"] == "today" and "RecallPeriod" not in registry["x.q01"]
    assert registry["x.score-total"]["HigherMeans"] == "more symptoms" and registry["x.score-total"]["LowerMeans"] == "fewer symptoms"

def test_missing_empty_or_non_text_values_are_left_out(tmp_path):
    lib, rec = _lib(tmp_path, study_extra={"RecallPeriod": ""}, score_extra={"HigherMeans": ["more"], "LowerMeans": 3})
    registry, problems = build_survey_registry(lib, rec)
    assert "RecallPeriod" not in registry["x"]
    assert "HigherMeans" not in registry["x.score-total"] and "LowerMeans" not in registry["x.score-total"]
```

If `_lib` does not take those keyword arguments, extend it minimally (default `None`, merged into the written JSON) rather than writing a second helper.

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_survey_terms.py -q`
Expected: the two new tests FAIL (KeyError `RecallPeriod`).

- [ ] **Step 3: Implement** in `build_survey_registry`: add a small helper `_set_text(term: dict, key: str, value) -> None` that sets `term[key] = _text(value)` only when it is non-empty (it already returns `""` for non-text); call it for the instrument (`study.get("RecallPeriod")`), each item (`item.get("RecallPeriod")`) and each score (`score.get("HigherMeans")`, `score.get("LowerMeans")`).
- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_survey_terms.py tests/test_cli_terms.py tests/test_term_registry.py -q`
Expected: PASS, and `python prism_tools.py terms show tipi.score-total --modality survey` still runs (the term JSON simply has the extra keys when a recipe sets them).

- [ ] **Step 5: Commit** `feat(terms): survey terms carry RecallPeriod, HigherMeans and LowerMeans`.

### Task 5: The template editor lists `RecallPeriod`; the docs say what the fields are

**Files:**
- Modify: `app/static/js/template-editor/questionnaire-sections.js` (the `administration` fields list, after `Study/ScoringTime`), `docs/CLI_REFERENCE.md`, the recipe documentation page that mentions `Interpretation` (find it with `grep -rln Interpretation docs | head`).
- Test: the existing JS test for the editor sections if one exists (`ls app/static/js/template-editor | grep -i test`); otherwise a Python test that reads the file and asserts the field name is listed.

**Interfaces:**
- Consumes: the vendored survey schema from Task 2 (the editor builds widgets from the schema; confirm that `Study/RecallPeriod` renders as a text field with the same widget as `Study/Instructions`, not a new one).

- [ ] **Step 1: Write the failing test.** JS test if the folder has one, else `tests/test_template_editor_sections.py`:

```python
from pathlib import Path

def test_the_administration_section_lists_recall_period():
    text = (Path(__file__).resolve().parents[1] / "app/static/js/template-editor/questionnaire-sections.js").read_text()
    assert "'Study/RecallPeriod'" in text
```

- [ ] **Step 2: Run to verify failure** (`python -m pytest tests/test_template_editor_sections.py -q`). Expected: FAIL.
- [ ] **Step 3: Add `'Study/RecallPeriod'`** to the `administration` fields; open the template editor in Studio (`python prism-studio.py`, template editor page) and check that the field appears and saves a value; if it renders wrongly, fix by reusing the `Study/Instructions` widget, not by a new one.
- [ ] **Step 4: Docs.** `docs/CLI_REFERENCE.md`: one sentence that `terms show --modality survey` also prints `RecallPeriod`, `HigherMeans` and `LowerMeans` when the template or recipe sets them. The recipe page: one row each for `HigherMeans` and `LowerMeans`.
- [ ] **Step 5: Run the checks and commit**

Run: `python -m pytest tests/test_template_editor_sections.py tests/test_survey_terms.py tests/test_vendored_specification.py -q` and `python tests/verify_repo.py --check dual-tree-drift --no-fix`
Expected: PASS. Commit `feat(template editor): RecallPeriod in the Administration section; docs for the new fields`.

---

## Self-Review

- **Spec coverage:** direction text (`HigherMeans`, `LowerMeans`): Tasks 3, 4; period (`RecallPeriod`, item override): Tasks 1, 4, 5; "the direction a program can read goes on the link": not here, step 4; "release v1.5.5 and sync": Task 2; respondent and range need nothing.
- **Rulings made here (the user can overrule):** `RecallPeriod` is free text (string or an object with `en`), not a validated ISO 8601 duration, because "past 2 weeks" and "P14D" are both honest answers and the check would refuse one of them; `HigherMeans` / `LowerMeans` are plain strings, like `Description` and `Note` in the same recipe schema, not language objects; the survey schema's minor version is bumped (2.1.0), as CONTRIBUTING.md asks for an added optional field; the recipe schema version stays unless a test pins it; no official template or recipe is filled in (agnostic principle; the fatigue pilot is step 4); the recipe builder page is not touched because its modules do not edit `Interpretation` or `Note` today (to be confirmed when Task 3 is built; a follow-up if it does).
- **Names used across tasks:** `Study.RecallPeriod`, item `RecallPeriod`, `HigherMeans`, `LowerMeans`, `build_survey_registry`, `_text`, `_set_text`: consistent.
- **Proportion:** five tasks, two repos; the plan is longer than the diff on purpose only where the release order matters.
