# Pavlovia Export Completion Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Supersedes:** `docs/superpowers/plans/2026-08-10-pavlovia-export-completion.md`. That
plan was written against an assumed data shape that no longer (or never actually)
matched the real, current survey schema — verified against `app/schemas/stable/
survey.schema.json` and a real shipped template (`examples/wellbeing_multi_demo/code/
library/survey/survey-wellbeing-multi.json`) before writing this one. See "What changed
from v1" below. Do not execute the v1 plan; its wiring-layer tasks (CLI/Flask/GUI) are
still conceptually sound and this plan reuses their approach, but every task touching
`extract_questions`/`determine_component_type`/`build_psyexp_xml` is replaced, not
patched.

**Goal:** Turn `src/converters/pavlovia.py` from an unwired, partially-broken script
into a working PRISM → Pavlovia/PsychoPy exporter, reachable from the CLI and the Studio
GUI the same way `generate_lss` is — scoped to single-language, active-variant-only
export (no import direction this round; see Global Constraints).

**Architecture:** No new module. `src/converters/pavlovia.py` stays the single
implementation. It gains: a language resolver, a variant resolver (replacing the
fictional `Items`/loop concept v1 was built around), a component-type classifier that
mirrors the Studio's own `detectQuestionType` (in `app/static/js/template-editor.js`)
instead of a nonexistent `QuestionType` field, and real per-type component builders. It
then gets the same three-layer wiring `generate_lss` already has: a CLI subcommand
(`survey export-pavlovia`), a Flask endpoint (`/api/generate-pavlovia`), and a Studio GUI
entry (Survey Export's tool selector, currently hardcoded to one option).

**Tech Stack:** stdlib `xml.etree`/`defusedxml` (already imported in the file), stdlib
`zipfile` for the multi-file download (new use, no new dependency), `pandas` (already
imported) for `conditions.csv`.

## What changed from v1 (why this plan exists)

Verified directly against a real template and the schema before writing a single task:

- **`Description` and `Levels` entries can be per-language objects**
  (`{"en": "...", "de": "..."}`), not always plain strings — schema explicitly allows
  both (`"type": ["string", "object"]`). v1's `extract_questions` did
  `value.get("Description", "")` assuming a string always; on a real bilingual template
  (like this repo's own Survey Authoring tutorial produces by its Chapter 4) it gets a
  dict, silently corrupting the export. Confirmed with `python3 -c "import json;
  print(json.load(open('examples/wellbeing_multi_demo/code/library/survey/
  survey-wellbeing-multi.json'))['WB01'])"`.
- **The `Items` (array sub-question) concept v1's Task 3 built an entire loop-routine
  feature around does not exist in the current schema at all** — grepping the full
  schema for the property name `Items` returns nothing. Multi-version handling is done
  via `VariantScales` (a list of per-variant scale overrides on each item) and
  `ApplicableVersions` (which variant IDs an item belongs to) instead. On any real
  template, `question.get("items")` is always falsy, so v1's Task 3 loop path was dead
  code solving a problem that no longer exists.
- **`Position.Group`-based routine splitting is also dead code for real data** — the
  `Group` value lives only in the *Excel authoring* sheet (used to split a
  multi-instrument workbook into separate template files at import time); it is never
  written into the resulting template JSON. `build_psyexp_xml`'s
  `q["position"].get("Group", "questions")` always falls back to the same default for
  every question in every real template, so the "one routine per group" structure it
  builds is really always "one routine," just via a roundabout, silently-always-hit
  default. This plan builds one routine directly instead of pretending grouping exists.
- **`Mandatory` defaults to the wrong value.** v1 read `question.get("mandatory", False)`;
  the actively-maintained `limesurvey_exporter.py` (confirmed at two call sites, e.g.
  `is_mandatory = q_data.get("Mandatory", True)`) defaults missing values to `True`,
  consistent with a recent bug fix (`24d8be96`, "honor PRISM Mandatory field in Quick
  Export LSS generation") this repo already shipped for the LimeSurvey path. Pavlovia
  should match, not diverge.
- **`ConditionalDisplay.showWhen` / `Relevance` / `LimeSurvey.Relevance` precedence
  (v1's Task 1 fix) is still correct** — confirmed against `_build_relevance_equation`
  in `app/src/limesurvey_exporter.py`, unchanged since v1 was written. Kept as-is below
  (Task 1).
- **The CLI/Flask/GUI wiring *pattern*** for `generate_lss` (parser → dispatch →
  entrypoint → command function; Flask handler → route; GUI `toolConfig` object) is
  still current — re-verified fresh against today's `app/src/cli/parser.py`,
  `dispatch.py`, `commands/survey.py`, `entrypoint.py`,
  `app/src/web/blueprints/tools_generation_handlers.py`, `tools.py`, and
  `app/static/js/survey-generator.js`. **The exact line numbers v1 cited are almost
  certainly stale** (several of these files changed since Aug 10 per `git log`) — every
  wiring task below anchors to grep-able function/variable names instead of line
  numbers, and each implementer must re-locate the exact insertion point at execution
  time rather than trust a cited line.

## Global Constraints

- **Single/base language only.** Resolve `I18n.DefaultLanguage` (fallback `"en"`) for
  every Description/Levels lookup; no `--language` flag, no multi-language output this
  round. A dict value resolves via `_resolve_text()` (Task 2); a plain string passes
  through unchanged (the schema explicitly allows both, so this must not break
  already-single-language templates).
- **Active/default variant only.** Resolve `Study.Version` (the template's declared
  default variant ID) once per export; no `--variant` flag, no picker. An item is
  included if it has no `ApplicableVersions` (applies to every variant — the common
  case for a non-multi-version template) or if the active variant ID is in that list
  (mirrors `template-editor.js`'s own `excludedByVariant` check exactly — do not
  reinvent this semantics, copy it). If the item has a `VariantScales` entry matching
  the active variant, that entry's `DataType`/`MinValue`/`MaxValue`/`Levels`/`ScaleType`
  override the item's own top-level values for this export; otherwise use the item's
  own top-level values.
- **Export only, no import this round.** `import_from_pavlovia` stays exactly as it is
  (an explicit "not yet implemented" stub) — do not touch it, do not wire it into any
  CLI/Flask/GUI surface. A future round can pick it up.
- **No new third-party dependency.** Everything below uses what's already imported in
  `pavlovia.py` (`defusedxml`, `pandas`) or the stdlib (`re`, `zipfile`).
- **Follow the existing CLI/web wiring pattern for `generate_lss` exactly** — same file
  layout, same handler shape — so this isn't a second, divergent way of wiring an
  exporter into the app. `pavlovia.py` only exists in `src/converters/` (no `app/src/`
  mirror) — keep it that way; this avoids a new instance of the dual-tree-drift failure
  mode `CLAUDE.md` documents.
- **Real PsychoPy Builder `.psyexp` schema is versioned and richer than what's
  practical to hand-verify without PsychoPy installed** (not available in this
  environment). Tests in this plan assert structural/round-trip correctness
  (well-formed XML, right component per question type, right params sourced from PRISM
  data) — they do **not** assert the file opens in actual PsychoPy Builder. Task 8 calls
  this out explicitly as a manual verification step for a human with PsychoPy
  installed; don't claim Builder-compatibility beyond what's actually been checked.
- **Session labels / string identifiers**: PRISM item codes (`ItemID`) are used verbatim
  elsewhere in this codebase (never normalized/zero-padded, per `CLAUDE.md`'s
  session-ID policy, which extends to any identifier PRISM treats as a free-form
  string) — `_safe_component_name()` (Task 3) only replaces characters PsychoPy
  component names structurally can't contain; it must not alter codes that are already
  valid.

---

## File Structure

- Modify: `src/converters/pavlovia.py` — language/variant resolvers, component
  classifier + builders, routine construction, Mandatory default (Tasks 1–4).
- Modify: `app/src/cli/parser.py` — new `export-pavlovia` subparser (Task 5).
- Modify: `app/src/cli/dispatch.py` — route the new action (Task 5).
- Modify: `app/src/cli/commands/survey.py` — new `cmd_survey_export_pavlovia` (Task 5).
- Modify: `app/src/cli/entrypoint.py` — wire the handler into the `handlers` dict
  (Task 5).
- Modify: `app/src/web/blueprints/tools_generation_handlers.py` — new
  `handle_generate_pavlovia_endpoint` (Task 6).
- Modify: `app/src/web/blueprints/tools.py` — new `/api/generate-pavlovia` route
  (Task 6).
- Modify: `app/static/js/survey-generator.js` — add a `pavlovia` entry to
  `toolConfig`, handle the `.zip` download (Task 7).
- Modify: `app/templates/survey_generator.html` — add
  `<option value="pavlovia">Pavlovia/PsychoPy</option>` to `#targetToolSelect`
  (Task 7).
- Create: `tests/test_pavlovia_exporter.py` — unit tests for Tasks 1–4.
- Create: `tests/test_cli_survey_export_pavlovia.py` — CLI integration test for Task 5,
  mirroring the existing LSS CLI test file's structure.

---

### Task 1: Fix the `Condition` extraction bug

`extract_questions()` currently reads `value.get("Condition", None)` — that key doesn't
exist anywhere in real PRISM survey JSON. The canonical field, used by
`_build_relevance_equation()` in `app/src/limesurvey_exporter.py`, is
`ConditionalDisplay.showWhen` (with `Relevance` / `LimeSurvey.Relevance` as
higher-priority overrides). As written, every question's `condition` is always `None`,
so nothing conditional ever survives into the Pavlovia export today. (Carried over from
v1 unchanged — this specific finding is still correct.)

**Files:**
- Modify: `src/converters/pavlovia.py` (`extract_questions` — grep for
  `"condition": value.get("Condition"` to find the exact current line; do not assume a
  line number)
- Test: `tests/test_pavlovia_exporter.py` (new file)

**Interfaces:**
- Produces: `_extract_condition(value: Dict[str, Any]) -> Optional[str]`. Downstream
  (Task 4) consumes `question["condition"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pavlovia_exporter.py
from src.converters.pavlovia import extract_questions


def test_extract_questions_reads_conditional_display_showwhen():
    prism_json = {
        "sex": {"Description": "Sex", "DataType": "string"},
        "pregnant": {
            "Description": "Are you pregnant?",
            "DataType": "string",
            "ConditionalDisplay": {"showWhen": "sex == 'F'"},
        },
    }
    questions = extract_questions(prism_json)
    by_code = {q["code"]: q for q in questions}
    assert by_code["pregnant"]["condition"] == "sex == 'F'"
    assert by_code["sex"]["condition"] is None


def test_extract_questions_prefers_explicit_relevance():
    prism_json = {
        "q1": {
            "Description": "Q1",
            "Relevance": "age >= 18",
            "ConditionalDisplay": {"showWhen": "sex == 'F'"},
        },
    }
    questions = extract_questions(prism_json)
    assert questions[0]["condition"] == "age >= 18"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: FAIL — `condition` is `None` for `pregnant` (still reading the nonexistent
`Condition` key).

- [ ] **Step 3: Write minimal implementation**

Add this helper near the top of `src/converters/pavlovia.py` (after the imports, before
`extract_questions`):

```python
def _extract_condition(value: Dict[str, Any]) -> Optional[str]:
    """Get the display-condition expression for a question, if any.

    Mirrors the precedence in app/src/limesurvey_exporter.py's
    _build_relevance_equation: explicit Relevance wins, then
    LimeSurvey.Relevance, then ConditionalDisplay.showWhen.
    """
    if "Relevance" in value:
        return value["Relevance"]
    limesurvey = value.get("LimeSurvey")
    if isinstance(limesurvey, dict) and "Relevance" in limesurvey:
        return limesurvey["Relevance"]
    conditional = value.get("ConditionalDisplay")
    if isinstance(conditional, dict):
        return conditional.get("showWhen") or None
    return None
```

In `extract_questions`, change the line reading `"condition": value.get("Condition",
None),` to `"condition": _extract_condition(value),`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "$(cat <<'EOF'
fix: pavlovia exporter reads ConditionalDisplay.showWhen instead of nonexistent Condition key

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Language and variant resolution

Replaces v1's dead "Items/loop" Task 3. Adds the real mechanism the current schema
uses for multi-language and multi-version templates, per Global Constraints above.

**Files:**
- Modify: `src/converters/pavlovia.py` (`extract_questions`, new helpers)
- Test: `tests/test_pavlovia_exporter.py`

**Interfaces:**
- Produces: `_resolve_text(value: Any, language: str) -> str`;
  `_get_active_variant_id(prism_json: Dict[str, Any]) -> Optional[str]`;
  `_resolve_item_for_variant(item: Dict[str, Any], variant_id: Optional[str]) ->
  Optional[Dict[str, Any]]` (returns `None` if the item is excluded by
  `ApplicableVersions`, otherwise the item dict with `DataType`/`MinValue`/`MaxValue`/
  `Levels`/`ScaleType` overridden from the matching `VariantScales` entry if one
  exists). `extract_questions` now calls these; each returned question dict gains a
  `raw_levels` key (the resolved `Levels` dict, still keyed by numeric string, values
  still possibly per-language) alongside the existing `levels` key (now a flat
  `{code: label_string}` dict — Task 3 consumes `levels` for choice building).

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_pavlovia_exporter.py
from src.converters.pavlovia import (
    extract_questions,
    _resolve_text,
    _get_active_variant_id,
    _resolve_item_for_variant,
)


def test_resolve_text_handles_plain_string():
    assert _resolve_text("Overall mood today", "en") == "Overall mood today"


def test_resolve_text_handles_language_dict():
    value = {"en": "Overall mood today", "de": "Stimmung heute"}
    assert _resolve_text(value, "de") == "Stimmung heute"


def test_resolve_text_falls_back_to_any_available_language():
    value = {"de": "Stimmung heute"}
    assert _resolve_text(value, "en") == "Stimmung heute"


def test_get_active_variant_id_reads_study_version():
    prism_json = {"Study": {"Version": "10-likert"}}
    assert _get_active_variant_id(prism_json) == "10-likert"


def test_get_active_variant_id_none_when_absent():
    assert _get_active_variant_id({"Study": {}}) is None
    assert _get_active_variant_id({}) is None


def test_resolve_item_for_variant_excludes_item_not_applicable():
    item = {"Description": "Q", "ApplicableVersions": ["7-likert"]}
    assert _resolve_item_for_variant(item, "10-likert") is None


def test_resolve_item_for_variant_includes_item_with_no_applicable_versions():
    item = {"Description": "Q"}
    assert _resolve_item_for_variant(item, "10-likert") == item


def test_resolve_item_for_variant_applies_variant_scale_override():
    item = {
        "Description": "Pain",
        "MinValue": 1,
        "MaxValue": 5,
        "ApplicableVersions": ["full", "short"],
        "VariantScales": [
            {"VariantID": "full", "ScaleType": "vas", "MinValue": 0, "MaxValue": 100},
        ],
    }
    resolved = _resolve_item_for_variant(item, "full")
    assert resolved["MinValue"] == 0
    assert resolved["MaxValue"] == 100
    assert resolved["ScaleType"] == "vas"


def test_extract_questions_resolves_language_and_excludes_wrong_variant():
    prism_json = {
        "Study": {"Version": "full"},
        "rec_mood": {
            "Description": {"en": "Mood today", "de": "Stimmung heute"},
            "Levels": {"1": {"en": "Low", "de": "Niedrig"}, "2": {"en": "High", "de": "Hoch"}},
            "ApplicableVersions": ["full", "short"],
        },
        "rec_extra": {
            "Description": "Full-only item",
            "ApplicableVersions": ["full"],
        },
        "rec_gone": {
            "Description": "Not in this variant",
            "ApplicableVersions": ["short"],
        },
    }
    questions = extract_questions(prism_json)
    codes = {q["code"] for q in questions}
    assert codes == {"rec_mood", "rec_extra"}
    mood = next(q for q in questions if q["code"] == "rec_mood")
    assert mood["description"] == "Mood today"
    assert mood["levels"] == {"1": "Low", "2": "High"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: FAIL — `_resolve_text`, `_get_active_variant_id`,
`_resolve_item_for_variant` don't exist yet; `extract_questions` doesn't filter by
variant or resolve language yet.

- [ ] **Step 3: Write minimal implementation**

Add these helpers to `src/converters/pavlovia.py`, near `_extract_condition`:

```python
def _resolve_text(value: Any, language: str) -> str:
    """Resolve a Description/Levels-label value to a plain string.

    The schema allows either a plain string or a per-language object
    ({"en": ..., "de": ...}). Prefer the requested language, fall back to
    any available language, fall back to empty string.
    """
    if isinstance(value, dict):
        if language in value:
            return str(value[language])
        for v in value.values():
            if v:
                return str(v)
        return ""
    if value is None:
        return ""
    return str(value)


def _get_active_variant_id(prism_json: Dict[str, Any]) -> Optional[str]:
    """The template's declared default/active variant, if any."""
    study = prism_json.get("Study")
    if isinstance(study, dict):
        version = study.get("Version")
        if version:
            return str(version)
    return None


def _resolve_item_for_variant(
    item: Dict[str, Any], variant_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Apply variant filtering/override to one item.

    Mirrors app/static/js/template-editor.js's own excludedByVariant check:
    an item with no (or empty) ApplicableVersions applies to every variant;
    otherwise it's excluded unless variant_id is explicitly listed.

    Returns the (possibly overridden) item dict, or None if excluded.
    """
    applicable = item.get("ApplicableVersions")
    if isinstance(applicable, list) and applicable and variant_id not in applicable:
        return None

    variant_scales = item.get("VariantScales")
    if variant_id and isinstance(variant_scales, list):
        for scale in variant_scales:
            if isinstance(scale, dict) and scale.get("VariantID") == variant_id:
                merged = dict(item)
                for key in ("DataType", "MinValue", "MaxValue", "Levels", "ScaleType", "Unit"):
                    if key in scale:
                        merged[key] = scale[key]
                return merged

    return item
```

Rewrite `extract_questions` to use them. Replace the function body with:

```python
def extract_questions(
    prism_json: Dict[str, Any], language: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Extract question data from PRISM JSON, filtering out metadata sections."""
    if language is None:
        i18n = prism_json.get("I18n")
        language = (
            i18n.get("DefaultLanguage")
            if isinstance(i18n, dict) and i18n.get("DefaultLanguage")
            else "en"
        )

    active_variant = _get_active_variant_id(prism_json)
    questions = []
    metadata_keys = {"Technical", "Study", "Metadata", "I18n", "Scoring", "Normative"}

    for key, value in prism_json.items():
        if key in metadata_keys or not isinstance(value, dict):
            continue

        resolved = _resolve_item_for_variant(value, active_variant)
        if resolved is None:
            continue

        raw_levels = resolved.get("Levels") if isinstance(resolved.get("Levels"), dict) else {}
        flat_levels = {
            level_key: _resolve_text(level_value, language)
            for level_key, level_value in raw_levels.items()
        }

        question = {
            "code": key,
            "description": _resolve_text(resolved.get("Description", ""), language),
            "levels": flat_levels,
            "raw_levels": raw_levels,
            "data_type": resolved.get("DataType", "string"),
            "scale_type": resolved.get("ScaleType"),
            "min_value": resolved.get("MinValue"),
            "max_value": resolved.get("MaxValue"),
            "mandatory": resolved.get("Mandatory", True),
            "condition": _extract_condition(resolved),
            "help": resolved.get("HelpText", None),
        }
        questions.append(question)

    return questions
```

This drops the old `type`/`items`/`position`-based fields entirely (nothing downstream
uses them once Tasks 3–4 land — `type` fed a `QuestionType` field that never existed in
real data, `items` fed the dead loop path, `position.Group`-based sorting/grouping is
replaced by Task 4's single-routine construction). Update the two tests from Task 1
(`test_extract_questions_reads_conditional_display_showwhen`,
`test_extract_questions_prefers_explicit_relevance`) to use `DataType: "string"` instead
of the now-removed `QuestionType` key in their fixtures, and confirm they still pass.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS (all tests, including the two from Task 1 after their fixture update)

- [ ] **Step 5: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "$(cat <<'EOF'
feat: add real language and variant resolution to pavlovia exporter

Description/Levels can be per-language objects per the schema; resolve
against I18n.DefaultLanguage (or "en"). Filter/override items by the
template's active variant (Study.Version) and VariantScales, mirroring
template-editor.js's own ApplicableVersions exclusion logic, replacing
the fictional Items/loop concept the previous version of this exporter
was built around.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Real component-type classification and builders

Replaces v1's Task 2. `determine_component_type` currently keys off a `QuestionType`
field that doesn't exist in real data and an `Items`-based "loop" case that's likewise
fictional. Rewrite it to mirror `detectQuestionType` in
`app/static/js/template-editor.js` (grep for `function detectQuestionType` to see its
current exact body before writing this task's implementation, in case it's changed
since this plan was written) — its precedence, adapted to the fields `extract_questions`
now actually produces: explicit `ScaleType` of `vas`/`visual-analogue` → slider;
non-empty `levels` with more than 10 entries → dropdown-style choice; non-empty
`levels` with 10 or fewer → radio-style choice; no levels → free-text.

**Files:**
- Modify: `src/converters/pavlovia.py` (`determine_component_type`,
  `create_psychopy_form_item`, new component builders)
- Test: `tests/test_pavlovia_exporter.py`

**Interfaces:**
- Consumes: `question["levels"]`, `question["scale_type"]` (from Task 2).
- Produces: `determine_component_type(question: Dict[str, Any]) -> str` returning one of
  `"slider"`, `"dropdown"`, `"radio"`, `"free_text"`; `_safe_component_name(code: str) ->
  str`; `create_slider_component(question) -> Dict[str, str]`;
  `create_textbox_component(question) -> Dict[str, str]`;
  `create_psychopy_form_item(question) -> Dict[str, Any]` (kept, now used only for
  radio/dropdown questions). Task 4 consumes all of these plus `_safe_component_name`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_pavlovia_exporter.py
from src.converters.pavlovia import (
    determine_component_type,
    _safe_component_name,
    create_slider_component,
    create_textbox_component,
)


def test_determine_component_type_vas_scale_is_slider():
    q = {"levels": {}, "scale_type": "vas", "min_value": 0, "max_value": 100}
    assert determine_component_type(q) == "slider"


def test_determine_component_type_visual_analogue_is_slider():
    q = {"levels": {}, "scale_type": "visual-analogue"}
    assert determine_component_type(q) == "slider"


def test_determine_component_type_few_levels_is_radio():
    q = {"levels": {"1": "Low", "2": "High"}, "scale_type": None}
    assert determine_component_type(q) == "radio"


def test_determine_component_type_many_levels_is_dropdown():
    q = {"levels": {str(i): f"L{i}" for i in range(12)}, "scale_type": None}
    assert determine_component_type(q) == "dropdown"


def test_determine_component_type_no_levels_is_free_text():
    q = {"levels": {}, "scale_type": None}
    assert determine_component_type(q) == "free_text"


def test_safe_component_name_replaces_invalid_characters():
    assert _safe_component_name("rec-mood.1") == "rec_mood_1"
    assert _safe_component_name("rec_mood") == "rec_mood"


def test_create_slider_component_uses_min_max():
    q = {"code": "rec_pain", "description": "Pain", "min_value": 0, "max_value": 100}
    comp = create_slider_component(q)
    assert comp["name"] == "rec_pain"
    assert "0" in comp["ticks"] and "100" in comp["ticks"]


def test_create_textbox_component_basic():
    q = {"code": "notes", "description": "Anything else?"}
    comp = create_textbox_component(q)
    assert comp["name"] == "notes"
    assert comp["prompt"] == "Anything else?"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: FAIL — `determine_component_type` still checks the old fields;
`_safe_component_name`, `create_slider_component`, `create_textbox_component` don't
exist.

- [ ] **Step 3: Write minimal implementation**

Replace `determine_component_type` entirely:

```python
def determine_component_type(question: Dict[str, Any]) -> str:
    """Classify a question into a PsychoPy component type.

    Mirrors detectQuestionType's precedence in app/static/js/template-editor.js,
    adapted to the fields extract_questions produces (Task 2): a question with
    no Levels and no vas/visual-analogue ScaleType is free text; a
    vas/visual-analogue ScaleType is a slider regardless of Levels; otherwise
    the Levels count decides between a radio-style and dropdown-style choice
    list, matching the >10-options threshold the Studio's own Preview uses.
    """
    scale_type = (question.get("scale_type") or "").lower()
    if scale_type in ("vas", "visual-analogue"):
        return "slider"

    levels = question.get("levels") or {}
    if levels:
        return "dropdown" if len(levels) > 10 else "radio"

    return "free_text"
```

Add `import re` to the top-level imports if not already present, then add:

```python
def _safe_component_name(code: str) -> str:
    """PsychoPy component names must be valid Python identifiers.

    Only replaces characters that are structurally invalid (not letters,
    digits, or underscore) -- an already-valid code passes through unchanged,
    per this plan's session-label/identifier constraint.
    """
    safe = re.sub(r"[^0-9a-zA-Z_]", "_", code)
    if safe and safe[0].isdigit():
        safe = f"_{safe}"
    return safe


def create_slider_component(question: Dict[str, Any]) -> Dict[str, str]:
    """Build a slider component dict for a VAS/visual-analogue question."""
    min_value = question.get("min_value")
    max_value = question.get("max_value")
    min_value = 0 if min_value is None else min_value
    max_value = 100 if max_value is None else max_value
    return {
        "name": _safe_component_name(question["code"]),
        "label": question.get("description", ""),
        "ticks": f"({min_value}, {max_value})",
        "granularity": "1",
    }


def create_textbox_component(question: Dict[str, Any]) -> Dict[str, str]:
    """Build a textbox component dict for a free-text question."""
    return {
        "name": _safe_component_name(question["code"]),
        "prompt": question.get("description", ""),
    }
```

Update `create_psychopy_form_item` to use `question["levels"]` (now always a flat
`{code: label}` dict per Task 2, never the old raw i18n-object shape) — its existing body
already does `for key, text in question["levels"].items(): choices.append(f"{key}:
{text}")`, which is already correct against the new shape; only its `mandatory` check
needs no change either (Task 2 already ensures `question["mandatory"]` defaults `True`).
Leave `create_psychopy_form_item` otherwise as-is.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "$(cat <<'EOF'
feat: classify pavlovia components by real scale/levels data, not fictional QuestionType

Mirrors template-editor.js's detectQuestionType precedence (vas/
visual-analogue -> slider, >10 Levels -> dropdown, else radio, no Levels
-> free text) against the fields Task 2's extract_questions actually
produces, replacing dead QuestionType/Items-based classification.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Real routine/component construction + Condition gating

Replaces v1's Task 2 (component routing) and Task 4 (condition gating) in one task,
since both now land in the same rewritten `build_psyexp_xml`. Drops the fictional
`Position.Group`-based multi-routine splitting (see "What changed from v1") in favor of
one routine holding every question, each routed to its real component type from Task 3.
A question with a non-null `condition` (Task 1) gets a `CodeComponent` that hides its
component when the condition is false.

**Files:**
- Modify: `src/converters/pavlovia.py` (`build_psyexp_xml`)
- Test: `tests/test_pavlovia_exporter.py`

**Interfaces:**
- Consumes: `determine_component_type`, `_safe_component_name`,
  `create_slider_component`, `create_textbox_component`, `create_psychopy_form_item`
  (Task 3); `question["condition"]` (Task 1).
- Produces: `build_psyexp_xml(task_name, questions, prism_metadata) -> str` (signature
  unchanged from today — callers in `export_to_pavlovia` need no change).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_pavlovia_exporter.py
from src.converters.pavlovia import build_psyexp_xml
import xml.etree.ElementTree as ET


def _sample_questions():
    return [
        {
            "code": "rec_mood", "description": "Mood", "levels": {"1": "Low", "2": "High"},
            "scale_type": None, "min_value": None, "max_value": None,
            "mandatory": True, "condition": None,
        },
        {
            "code": "rec_pain", "description": "Pain", "levels": {},
            "scale_type": "vas", "min_value": 0, "max_value": 100,
            "mandatory": True, "condition": None,
        },
        {
            "code": "notes", "description": "Notes", "levels": {},
            "scale_type": None, "min_value": None, "max_value": None,
            "mandatory": False, "condition": "rec_mood == '1'",
        },
    ]


def test_build_psyexp_xml_is_well_formed():
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)  # raises if malformed
    assert root.tag == "PsychoPy2experiment"


def test_build_psyexp_xml_routes_slider_component():
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    slider_names = [
        c.get("name") for c in root.iter("SliderComponent")
    ]
    assert "rec_pain" in slider_names


def test_build_psyexp_xml_routes_textbox_component():
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    textbox_names = [c.get("name") for c in root.iter("TextboxComponent")]
    assert "notes" in textbox_names


def test_build_psyexp_xml_adds_code_component_for_conditional_question():
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    code_components = list(root.iter("CodeComponent"))
    assert len(code_components) == 1
    assert code_components[0].get("name") == "notes_condition"


def test_build_psyexp_xml_single_routine_for_all_questions():
    xml_str = build_psyexp_xml("recovery", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    question_routines = [
        r for r in root.iter("Routine") if r.get("name") not in ("welcome", "thanks")
    ]
    assert len(question_routines) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: FAIL — everything still routes to `FormComponent`, no `SliderComponent`/
`TextboxComponent`/`CodeComponent` exist, and questions are still split by the dead
`Group` default.

- [ ] **Step 3: Write minimal implementation**

Replace the "2. Question routines" section of `build_psyexp_xml` (from the
`grouped_questions` block through the end of that loop) with a single routine:

```python
    # 2. Question routine (single routine for all questions -- Position.Group
    # doesn't exist in real template JSON, see plan's "What changed from v1")
    routine = ET.SubElement(routines, "Routine")
    routine.set("name", "questions")

    form_items = []
    for q in questions:
        component_type = determine_component_type(q)
        safe_name = _safe_component_name(q["code"])

        if component_type == "slider":
            component = ET.SubElement(routine, "SliderComponent")
            component.set("name", safe_name)
            slider_params = create_slider_component(q)
            for key, value in slider_params.items():
                if key != "name":
                    _add_component_param(component, key, value)
        elif component_type == "free_text":
            component = ET.SubElement(routine, "TextboxComponent")
            component.set("name", safe_name)
            textbox_params = create_textbox_component(q)
            for key, value in textbox_params.items():
                if key != "name":
                    _add_component_param(component, key, value)
        else:
            # radio / dropdown -- batch into the shared form item list
            form_items.append(create_psychopy_form_item(q))

        if q.get("condition"):
            code_component = ET.SubElement(routine, "CodeComponent")
            code_component.set("name", f"{safe_name}_condition")
            _add_component_param(
                code_component, "Begin Routine",
                f"{safe_name}_visible = bool({q['condition']!r})",
            )

    if form_items:
        form_component = ET.SubElement(routine, "FormComponent")
        form_component.set("name", "form_questions")
        _add_component_param(form_component, "items", str(form_items))
        _add_component_param(form_component, "randomize", "False")
```

Then update the "Flow" section — replace the loop `for group_name in
grouped_questions.keys(): ...` with a single fixed entry:

```python
    # Add the single question routine
    flow_item = ET.SubElement(flow, "Routine")
    flow_item.set("name", "questions")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "$(cat <<'EOF'
feat: route pavlovia components by real type, drop fictional group routines

Every question now lands in a real SliderComponent/TextboxComponent/
FormComponent choice based on Task 3's classification instead of always
FormComponent, in a single routine (Position.Group never exists in real
template JSON, so the old per-group routine split was always a no-op).
Conditional questions (Task 1) get a CodeComponent gate.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: CLI wiring — `survey export-pavlovia`

Mirrors the existing `survey export-lss` wiring exactly (grep each file below for
`export-lss`/`export_lss` to find today's exact pattern and insertion point — do not
assume v1's cited line numbers still apply, these files have changed since).

**Files:**
- Modify: `app/src/cli/parser.py` (new subparser, alongside `export-lss`'s)
- Modify: `app/src/cli/dispatch.py` (new `elif args.action == "export-pavlovia":`
  branch, alongside `export-lss`'s)
- Modify: `app/src/cli/commands/survey.py` (new `cmd_survey_export_pavlovia`, alongside
  `cmd_survey_export_lss`)
- Modify: `app/src/cli/entrypoint.py` (import + register the new handler, alongside
  `cmd_survey_export_lss`'s registration)
- Test: `tests/test_cli_survey_export_pavlovia.py` (new file)

**Interfaces:**
- Consumes: `export_to_pavlovia(json_path, output_dir=None, experiment_name=None) ->
  Path` (`src/converters/pavlovia.py`, unchanged signature).
- Produces: CLI action `survey export-pavlovia <json_path> [--output DIR]
  [--experiment-name NAME]`.

- [ ] **Step 1: Write the failing test**

First find an existing CLI integration test to mirror — run `ls tests/ | grep -i
"cli.*survey.*export\|export.*lss"` to find it (v1 assumed
`tests/test_cli_survey_export_commands.py`; confirm that's still the right file to
model, or find whichever one currently covers `cmd_survey_export_lss`). Then write:

```python
# tests/test_cli_survey_export_pavlovia.py
import json
import subprocess
import sys
from pathlib import Path


def test_cli_export_pavlovia_creates_psyexp(tmp_path):
    prism_json = tmp_path / "task-demo_survey.json"
    prism_json.write_text(
        json.dumps({"Study": {"TaskName": "demo"}, "q1": {"Description": "Q1"}}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    result = subprocess.run(
        [
            sys.executable, "-m", "src.cli.entrypoint",
            "survey", "export-pavlovia", str(prism_json), "--output", str(output_dir),
        ],
        cwd=str(Path(__file__).resolve().parents[1] / "app"),
        capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "demo.psyexp").exists()
```

(Adjust the invocation to however the existing LSS CLI test actually shells out — mirror
it exactly, e.g. it may invoke `prism_tools.py` directly rather than
`python -m src.cli.entrypoint`; use whichever the existing test file does.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_survey_export_pavlovia.py -v`
Expected: FAIL — `export-pavlovia` isn't a recognized action yet.

- [ ] **Step 3: Write minimal implementation**

In `app/src/cli/parser.py`, alongside the `export-lss` subparser, add:

```python
    parser_survey_export_pavlovia = survey_subparsers.add_parser(
        "export-pavlovia",
        help="Export a PRISM survey template to a Pavlovia/PsychoPy experiment",
    )
    parser_survey_export_pavlovia.add_argument(
        "json_path", help="Path to the PRISM survey template JSON"
    )
    parser_survey_export_pavlovia.add_argument(
        "--output", default=None, help="Output directory (default: alongside the input file)"
    )
    parser_survey_export_pavlovia.add_argument(
        "--experiment-name", default=None, help="Override the experiment/task name"
    )
```

In `app/src/cli/dispatch.py`, alongside the `export-lss` branch, add:

```python
        elif args.action == "export-pavlovia":
            handlers["survey_export_pavlovia"](args)
```

In `app/src/cli/commands/survey.py`, alongside `cmd_survey_export_lss`, add:

```python
def cmd_survey_export_pavlovia(args) -> None:
    """Handle the `survey export-pavlovia` CLI action.

    Delegates to src.converters.pavlovia.export_to_pavlovia. See that
    function's docstring for output layout.
    """
    from pathlib import Path
    from src.converters.pavlovia import export_to_pavlovia

    json_path = Path(args.json_path)
    if not json_path.exists():
        print(f"Error: {json_path} not found")
        raise SystemExit(1)

    output_dir = Path(args.output) if args.output else None
    psyexp_path = export_to_pavlovia(json_path, output_dir, args.experiment_name)
    print(f"Exported: {psyexp_path}")
```

In `app/src/cli/entrypoint.py`, add `cmd_survey_export_pavlovia` to the import from
`app/src/cli/commands/survey.py` (alongside `cmd_survey_export_lss`), and register it
in the `handlers` dict: `"survey_export_pavlovia": cmd_survey_export_pavlovia,`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_survey_export_pavlovia.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/src/cli/parser.py app/src/cli/dispatch.py app/src/cli/commands/survey.py \
        app/src/cli/entrypoint.py tests/test_cli_survey_export_pavlovia.py
git commit -m "$(cat <<'EOF'
feat: add `survey export-pavlovia` CLI command

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Web backend wiring — `/api/generate-pavlovia`

A Pavlovia export produces a directory (`.psyexp` + `conditions.csv` + `README.md`), so
the endpoint zips the output directory with stdlib `zipfile` before sending it — same
approach as the existing `template-export` ZIP download. Mirrors
`handle_generate_lss_endpoint` — grep for that name to find today's exact surrounding
code before editing (v1's cited line numbers are stale).

**Files:**
- Modify: `app/src/web/blueprints/tools_generation_handlers.py` (new handler, alongside
  `handle_generate_lss_endpoint`)
- Modify: `app/src/web/blueprints/tools.py` (new route + import, alongside the
  `generate-lss` route)
- Test: `tests/test_tools_generation_handlers.py` (extend existing file)

**Interfaces:**
- Consumes: `export_to_pavlovia` (`src/converters/pavlovia.py`).
- Produces: Flask route `POST /api/generate-pavlovia`, request body
  `{"files": [{"path": ...}], "experiment_name": <optional str>}`, response: a `.zip`
  file download.

- [ ] **Step 1: Write the failing test**

Read the existing test(s) for `handle_generate_lss_endpoint` in
`tests/test_tools_generation_handlers.py` first, to find the exact fixture name/shape
used for the Flask test client, then add:

```python
# add to tests/test_tools_generation_handlers.py
def test_handle_generate_pavlovia_endpoint_returns_zip(app_client, tmp_path):
    prism_json = tmp_path / "task-demo_survey.json"
    prism_json.write_text(
        '{"Study": {"TaskName": "demo"}, "q1": {"Description": "Q1"}}',
        encoding="utf-8",
    )

    response = app_client.post(
        "/api/generate-pavlovia",
        json={"files": [{"path": str(prism_json)}]},
    )

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
```

(Use whatever fixture name `app_client` actually is in that file — it may differ; match
it exactly rather than inventing a new one.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools_generation_handlers.py -v -k pavlovia`
Expected: FAIL — 404, route doesn't exist yet.

- [ ] **Step 3: Write minimal implementation**

In `app/src/web/blueprints/tools_generation_handlers.py`, alongside
`handle_generate_lss_endpoint`, add (adding `import zipfile` to the top-level imports if
not already present, alongside the existing `os`/`sys`/`tempfile`/`Path` imports):

```python
def handle_generate_pavlovia_endpoint():
    """Generate a Pavlovia/PsychoPy experiment .zip from a selected PRISM JSON file."""
    try:
        from src.converters.pavlovia import export_to_pavlovia
    except ImportError:
        export_to_pavlovia = None

    if not export_to_pavlovia:
        return jsonify({"error": "Pavlovia exporter not available"}), 500

    try:
        data, payload_error = _require_json_object_payload()
        if payload_error is not None:
            return payload_error

        file_paths = _extract_file_paths(data.get("files", []))
        if not file_paths:
            return jsonify({"error": "No files selected"}), 400
        if len(file_paths) > 1:
            return jsonify(
                {"error": "Pavlovia export supports one survey file at a time"}
            ), 400

        json_path = Path(file_paths[0])
        if not json_path.exists():
            return jsonify({"error": "File not found"}), 404

        experiment_name = data.get("experiment_name") or None

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "export"
            export_to_pavlovia(json_path, output_dir, experiment_name)

            zip_fd, zip_path = tempfile.mkstemp(suffix=".zip")
            os.close(zip_fd)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in output_dir.rglob("*"):
                    if file_path.is_file():
                        zf.write(file_path, file_path.relative_to(output_dir))

            download_filename = f"{output_dir.name}_pavlovia.zip"

        response = send_file(
            zip_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype="application/zip",
        )
        response.call_on_close(lambda: os.unlink(zip_path))
        return response
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
```

(Note `download_filename` is computed *before* the `with tempfile.TemporaryDirectory()`
block exits, since `output_dir` lives inside it — reference it after exit only via the
already-captured string, not `output_dir` itself.)

In `app/src/web/blueprints/tools.py`, add `handle_generate_pavlovia_endpoint` to the
import block alongside `handle_generate_lss_endpoint`, and alongside the `generate-lss`
route, add:

```python
@tools_bp.route("/api/generate-pavlovia", methods=["POST"])
def generate_pavlovia_endpoint():
    """Generate a Pavlovia/PsychoPy experiment from a selected PRISM JSON file."""
    return handle_generate_pavlovia_endpoint()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools_generation_handlers.py -v -k pavlovia`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/src/web/blueprints/tools_generation_handlers.py \
        app/src/web/blueprints/tools.py tests/test_tools_generation_handlers.py
git commit -m "$(cat <<'EOF'
feat: add /api/generate-pavlovia endpoint returning a zipped experiment

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Studio GUI wiring

Adds Pavlovia as a second option in Survey Export's tool selector, currently hardcoded
to one option. Grep for `toolConfig` in `app/static/js/survey-generator.js` and
`targetToolSelect` in `app/templates/survey_generator.html` to find today's exact
surrounding code before editing.

**Files:**
- Modify: `app/templates/survey_generator.html` (`#targetToolSelect` options)
- Modify: `app/static/js/survey-generator.js` (`toolConfig` object, export button
  handler, zip-download handling)

**Interfaces:**
- Consumes: `POST /api/generate-pavlovia` (Task 6).
- Produces: a working `Pavlovia/PsychoPy` option in the GUI's tool selector, whose
  export button downloads the `.zip` the endpoint returns.

- [ ] **Step 1: Manual verification plan (no automated GUI test in this plan)**

This task has no unit test — `survey-generator.js`'s existing test coverage (if any;
check `tests/` for a JS test runner before assuming there is none) doesn't cover the
tool selector, and standing up a browser test harness is out of scope for this plan.
Instead, Task 8's manual verification step (below) includes clicking through this GUI
path as part of its checklist. Proceed directly to implementation.

- [ ] **Step 2: Add the GUI option**

In `app/templates/survey_generator.html`, in `#targetToolSelect`, add a second
`<option>` alongside the existing `<option value="limesurvey">LimeSurvey</option>`:

```html
<option value="pavlovia">Pavlovia/PsychoPy</option>
```

In `app/static/js/survey-generator.js`, in the `toolConfig` object, add an entry
alongside the existing `limesurvey` one:

```js
pavlovia: { label: 'Pavlovia/PsychoPy', exportEndpoint: '/api/generate-pavlovia', fileExt: '.zip', optionsClass: 'tool-options-pavlovia' },
```

Find every place the code branches on `getSelectedTool() === 'limesurvey'` (there were
at least two such checks as of this plan's writing — re-grep to confirm the current
count and locations) and read what each one actually gates (e.g. LimeSurvey-specific
export-language checkboxes, matrix-grouping options). For each: if the gated UI/logic is
genuinely LimeSurvey-specific (doesn't apply to a Pavlovia/PsychoPy export at all —
matrix-grouping and per-question LimeSurvey settings almost certainly aren't), leave
those checks as `=== 'limesurvey'` unchanged (Pavlovia simply skips that UI, which is
correct — it needs no LimeSurvey-specific options). Only add a
`getSelectedTool() === 'pavlovia'` branch if the download/response handling itself needs
to differ (a `.zip` blob download is likely handled generically already via
`toolConfig[tool].fileExt`, matching the pattern the existing code uses for
`.lss` — verify this by reading the export-button click handler before assuming a new
branch is needed; add one only if the existing generic path doesn't already cover a
`.zip` extension correctly).

- [ ] **Step 3: Commit**

```bash
git add app/templates/survey_generator.html app/static/js/survey-generator.js
git commit -m "$(cat <<'EOF'
feat: add Pavlovia/PsychoPy option to Survey Export's tool selector

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: End-to-end regression test + manual PsychoPy verification note

**Files:**
- Test: `tests/test_pavlovia_exporter.py` (extend)

**Interfaces:**
- Consumes: `export_to_pavlovia` (all prior tasks).

- [ ] **Step 1: Write the end-to-end test**

```python
# add to tests/test_pavlovia_exporter.py
import json
from src.converters.pavlovia import export_to_pavlovia
import xml.etree.ElementTree as ET


def test_export_to_pavlovia_end_to_end(tmp_path):
    """A realistic bilingual, two-variant template exports cleanly."""
    prism_json = {
        "I18n": {"Languages": ["en", "de"], "DefaultLanguage": "en"},
        "Study": {"TaskName": "recovery", "Version": "full"},
        "rec_mood": {
            "Description": {"en": "Overall mood today", "de": "Stimmung heute"},
            "Levels": {
                "1": {"en": "Not at all", "de": "Gar nicht"},
                "2": {"en": "Slightly", "de": "Etwas"},
            },
            "DataType": "integer", "MinValue": 1, "MaxValue": 2,
            "ApplicableVersions": ["full", "short"],
        },
        "rec_pain": {
            "Description": {"en": "Pain intensity", "de": "Schmerzintensitaet"},
            "DataType": "integer", "MinValue": 0, "MaxValue": 100,
            "ApplicableVersions": ["full", "short"],
            "VariantScales": [
                {"VariantID": "full", "ScaleType": "vas", "MinValue": 0, "MaxValue": 100},
            ],
        },
        "rec_extra": {
            "Description": {"en": "Full-only extra item"},
            "ApplicableVersions": ["full"],
        },
        "rec_notes": {
            "Description": {"en": "Anything else?"},
            "Mandatory": False,
        },
    }
    json_path = tmp_path / "task-recovery_survey.json"
    json_path.write_text(json.dumps(prism_json), encoding="utf-8")

    psyexp_path = export_to_pavlovia(json_path, tmp_path / "out")

    assert psyexp_path.exists()
    root = ET.fromstring(psyexp_path.read_text(encoding="utf-8"))

    slider_names = [c.get("name") for c in root.iter("SliderComponent")]
    assert "rec_pain" in slider_names  # vas override applied

    textbox_names = [c.get("name") for c in root.iter("TextboxComponent")]
    assert "rec_notes" in textbox_names  # no Levels -> free text

    # rec_mood's English label made it through (default language resolution)
    all_param_values = " ".join(
        p.get("val", "") for p in root.iter("Param")
    )
    assert "Overall mood today" in all_param_values
    assert "Stimmung heute" not in all_param_values  # German NOT exported (single-language scope)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS (this and every test from Tasks 1–4)

- [ ] **Step 3: Run the full pavlovia + CLI + web test files together**

Run: `pytest tests/test_pavlovia_exporter.py tests/test_cli_survey_export_pavlovia.py tests/test_tools_generation_handlers.py -v`
Expected: all PASS, pristine output (no stray warnings)

- [ ] **Step 4: Commit**

```bash
git add tests/test_pavlovia_exporter.py
git commit -m "$(cat <<'EOF'
test: add end-to-end pavlovia export regression test

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Manual verification note (not automatable in this environment)**

PsychoPy isn't installed in this environment, so no task in this plan asserts the
produced `.psyexp` actually opens in PsychoPy Builder — only that it's well-formed XML
with the right components/params sourced from PRISM data. Record this plan's completion
with an explicit note that a human with PsychoPy installed should: (1) run `survey
export-pavlovia` against a real project template (e.g. this repo's own
`examples/wellbeing_multi_demo/code/library/survey/survey-wellbeing-multi.json`), (2)
open the resulting `.psyexp` in PsychoPy Builder, (3) confirm it loads without a schema
error and the routine's components render as expected, (4) confirm the GUI path (Task
7) produces the same file via a browser click-through. File any Builder-compatibility
gaps found as a follow-up, separate from this plan.

---

## Self-Review

**Spec coverage:** Every "What changed from v1" item has a task: Condition (Task 1),
language/variant resolution (Task 2), component classification (Task 3), routine
construction + conditional gating (Task 4), Mandatory default (fixed inline in Task 2's
`extract_questions` rewrite), CLI/Flask/GUI wiring (Tasks 5–7), end-to-end + manual
verification (Task 8). Import direction explicitly out of scope per Global Constraints.

**Placeholder scan:** No TBD/TODO. Task 7 has no automated test by design (documented
reason given, folded into Task 8's manual checklist instead of silently skipped).

**Type consistency:** `extract_questions` (Task 2) is the single producer of the
question dict shape (`code`, `description`, `levels`, `raw_levels`, `data_type`,
`scale_type`, `min_value`, `max_value`, `mandatory`, `condition`, `help`); Tasks 3–4
consume exactly those keys, no others invented or assumed.
