# Pavlovia Export Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `src/converters/pavlovia.py` from an unwired, half-implemented script into a
working PRISM → Pavlovia/PsychoPy exporter that actually does what
`docs/PAVLOVIA_EXPORT.md` already claims, reachable from the CLI and the Studio GUI
the same way `generate_lss` is.

**Architecture:** No new module. `src/converters/pavlovia.py` stays the single
implementation; it gains real per-question-type component builders, a loop/conditions
path for array questions, a Condition→CodeComponent path, and a real CSV import. It then
gets the same three-layer wiring `generate_lss` already has: a CLI subcommand
(`survey export-pavlovia`), a Flask endpoint (`/api/generate-pavlovia`), and a Studio GUI
entry (Survey Generator's existing, currently single-option, tool selector).

**Tech Stack:** stdlib `xml.etree`/`defusedxml` (already used), stdlib `zipfile` for the
multi-file download (new use, no new dependency), `pandas` (already used) for
`conditions.csv`.

## Global Constraints

- No new third-party dependency. Everything below uses what's already imported in
  `pavlovia.py` (`defusedxml`, `pandas`) or the stdlib (`re`, `zipfile`).
- Follow the existing CLI/web wiring pattern for `generate_lss` exactly — same file
  layout, same handler shape — so this isn't a second, divergent way of wiring an
  exporter into the app (see `docs/superpowers/plans/` sibling plans for the same
  dual-tree-drift concern CLAUDE.md documents; this task avoids creating a new instance
  of it by adding no new `src/` vs `app/src/` mirror — `pavlovia.py` only exists in
  `src/converters/`, keep it that way).
- Real PsychoPy Builder `.psyexp` schema is versioned and richer than what's practical to
  hand-verify without PsychoPy installed (not available in this environment). Tests in
  this plan assert structural/round-trip correctness (well-formed XML, right component
  per question type, right params sourced from PRISM data) — they do **not** assert the
  file opens in actual PsychoPy Builder. Task 9 calls this out explicitly as a manual
  verification step for a human with PsychoPy installed; don't claim Builder-compatibility
  beyond what's actually been checked.
- Session labels / string identifiers: PRISM question codes are used verbatim as-is
  elsewhere in this codebase (never normalized/zero-padded per CLAUDE.md's session-ID
  policy) — the new `_safe_component_name()` in Task 2 only replaces characters PsychoPy
  component names structurally can't contain; it must not alter codes that are already
  valid.

---

## File Structure

- Modify: `src/converters/pavlovia.py` — component builders, loop wiring, condition
  wiring, CSV import (Tasks 1–5).
- Modify: `app/src/cli/parser.py` — new `export-pavlovia` subparser (Task 6).
- Modify: `app/src/cli/dispatch.py` — route the new action (Task 6).
- Modify: `app/src/cli/commands/survey.py` — new `cmd_survey_export_pavlovia` (Task 6).
- Modify: `app/src/cli/entrypoint.py` — wire the handler into the `handlers` dict (Task 6).
- Modify: `app/src/web/blueprints/tools_generation_handlers.py` — new
  `handle_generate_pavlovia_endpoint` (Task 7).
- Modify: `app/src/web/blueprints/tools.py` — new `/api/generate-pavlovia` route (Task 7).
- Modify: `app/static/js/survey-generator.js` — uncomment/add `pavlovia` tool config
  entry, handle zip download (Task 8).
- Modify: `app/templates/survey_generator.html` — add `<option value="pavlovia">` to
  `#targetToolSelect` (Task 8).
- Create: `tests/test_pavlovia_exporter.py` — unit tests for Tasks 1–5.
- Create: `tests/test_cli_survey_export_pavlovia.py` — CLI integration test for Task 6,
  mirroring `tests/test_cli_survey_export_commands.py`.

---

### Task 1: Fix the `Condition` extraction bug

`extract_questions()` currently reads `value.get("Condition", None)` (pavlovia.py:57) — that
key doesn't exist anywhere in real PRISM survey JSON. The canonical field, used by
`_build_relevance_equation()` in `app/src/limesurvey_exporter.py:449`, is
`ConditionalDisplay.showWhen` (with `Relevance` / `LimeSurvey.Relevance` as
higher-priority overrides). As written, every question's `condition` is always `None`,
so nothing conditional ever survives into the Pavlovia export today.

**Files:**
- Modify: `src/converters/pavlovia.py:43-71` (`extract_questions`)
- Test: `tests/test_pavlovia_exporter.py` (new file)

**Interfaces:**
- Produces: `extract_questions(prism_json)` now returns each question dict with
  `condition` set to the `showWhen` string (or explicit `Relevance` string) instead of
  always `None`. Downstream tasks (Task 4) consume `question["condition"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pavlovia_exporter.py
from src.converters.pavlovia import extract_questions


def test_extract_questions_reads_conditional_display_showwhen():
    prism_json = {
        "sex": {"Description": "Sex", "QuestionType": "text"},
        "pregnant": {
            "Description": "Are you pregnant?",
            "QuestionType": "text",
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

Replace the `"condition": value.get("Condition", None)` line in `extract_questions`:

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

In `extract_questions`, change:
```python
                "condition": value.get("Condition", None),
```
to:
```python
                "condition": _extract_condition(value),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "fix: pavlovia exporter reads ConditionalDisplay.showWhen instead of nonexistent Condition key"
```

---

### Task 2: Route each question to its real component type

`build_psyexp_xml` currently ignores `determine_component_type()` entirely and always
emits a `FormComponent` (pavlovia.py:242). Wire it up: slider-classified questions get a
`SliderComponent`, textbox-classified questions get a `TextboxComponent`, loop-classified
questions are skipped here (Task 3 gives them their own routine), everything else
still batches into the group's `FormComponent` as before.

**Files:**
- Modify: `src/converters/pavlovia.py` (imports, new helpers, `build_psyexp_xml`)
- Test: `tests/test_pavlovia_exporter.py`

**Interfaces:**
- Consumes: `determine_component_type(question) -> "slider"|"textbox"|"loop"|"form"`
  (pavlovia.py:74, already defined, previously dead).
- Produces: `_safe_component_name(code: str) -> str`; `create_slider_component(question)
  -> Dict[str, str]`; `create_textbox_component(question) -> Dict[str, str]`. Task 3 and
  Task 4 both call `_safe_component_name`.

- [ ] **Step 1: Write the failing test**

```python
from src.converters.pavlovia import build_psyexp_xml
import xml.etree.ElementTree as ET


def _sample_questions():
    return [
        {
            "code": "mood_1", "description": "How sad do you feel?",
            "type": "text", "levels": {"0": "Not at all", "1": "A little",
                                        "2": "Moderately", "3": "Extremely"},
            "items": {}, "mandatory": True, "condition": None, "help": None,
            "position": {"Group": "mood", "GroupOrder": 0, "QuestionOrder": 0},
        },
        {
            "code": "comments", "description": "Anything else to add?",
            "type": "long_free_text", "levels": {}, "items": {},
            "mandatory": False, "condition": None, "help": None,
            "position": {"Group": "mood", "GroupOrder": 0, "QuestionOrder": 1},
        },
    ]


def test_slider_question_gets_slider_component():
    xml_str = build_psyexp_xml("demo", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    sliders = root.findall(".//SliderComponent")
    assert len(sliders) == 1
    assert sliders[0].get("name") == "slider_mood_1"


def test_freetext_question_gets_textbox_component():
    xml_str = build_psyexp_xml("demo", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    textboxes = root.findall(".//TextboxComponent")
    assert len(textboxes) == 1
    assert textboxes[0].get("name") == "textbox_comments"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: FAIL — no `SliderComponent`/`TextboxComponent` elements exist yet (everything
is a `FormComponent`).

- [ ] **Step 3: Write minimal implementation**

Add near the top of `pavlovia.py` (after the existing imports):
```python
import re
```

Add after `create_psychopy_form_item` (pavlovia.py:174):

```python
def _safe_component_name(code: str) -> str:
    """Sanitize a PRISM question code into a valid PsychoPy component name.

    PsychoPy component names must be valid Python identifiers. This only
    replaces characters that make that untrue — it must not alter codes
    that are already valid (PRISM question codes are user data, not ours
    to renormalize).
    """
    name = re.sub(r"[^0-9a-zA-Z_]", "_", code)
    if not name or name[0].isdigit():
        name = f"q_{name}"
    return name


def create_slider_component(question: Dict[str, Any]) -> Dict[str, str]:
    """Build Param values for a PsychoPy Slider component (Likert-style item)."""
    levels = question.get("levels", {})
    numeric_keys = sorted(int(k) for k in levels.keys())
    labels = [levels[str(k)] for k in numeric_keys]
    return {
        "text": question["description"],
        "ticks": str(numeric_keys),
        "labels": str(labels),
        "granularity": "1",
    }


def create_textbox_component(question: Dict[str, Any]) -> Dict[str, str]:
    """Build Param values for a PsychoPy Textbox component (free-text item)."""
    return {
        "prompt": question["description"],
        "editable": "True",
        "required": "True" if question.get("mandatory") else "False",
    }
```

Replace the group-building loop in `build_psyexp_xml` (pavlovia.py:230-246):

```python
    for group_name, group_questions in grouped_questions.items():
        routine = ET.SubElement(routines, "Routine")
        routine_name = f"group_{group_name.lower().replace(' ', '_')}"
        routine.set("name", routine_name)

        form_items = []
        for q in group_questions:
            component_type = determine_component_type(q)
            safe_q_name = _safe_component_name(q["code"])

            if component_type == "slider":
                slider = ET.SubElement(routine, "SliderComponent")
                slider.set("name", f"slider_{safe_q_name}")
                for pname, pval in create_slider_component(q).items():
                    _add_component_param(slider, pname, pval)
            elif component_type == "textbox":
                textbox = ET.SubElement(routine, "TextboxComponent")
                textbox.set("name", f"textbox_{safe_q_name}")
                for pname, pval in create_textbox_component(q).items():
                    _add_component_param(textbox, pname, pval)
            elif component_type == "loop":
                continue  # Task 3 gives loop questions their own routine
            else:
                form_items.append(create_psychopy_form_item(q))

        if form_items:
            form_component = ET.SubElement(routine, "FormComponent")
            form_component.set("name", f"form_{routine_name}")
            _add_component_param(form_component, "items", str(form_items))
            _add_component_param(form_component, "randomize", "False")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "feat: route pavlovia questions to slider/textbox/form components by type"
```

---

### Task 3: Loop routine for array (Items) questions

Array questions (`items` present) currently produce rows in `conditions.csv` (already
implemented, `create_conditions_csv`) but nothing in the `.psyexp` ever references that
CSV — the subquestions are silently dropped from the experiment. Give each loop-type
question its own `Routine` (a `FormComponent` driven by `$conditions`) plus a
`LoopInitiator`/`LoopTerminator` pair in `Flow` pointing at `conditions.csv`.

**Files:**
- Modify: `src/converters/pavlovia.py` (`build_psyexp_xml`)
- Test: `tests/test_pavlovia_exporter.py`

**Interfaces:**
- Consumes: `_safe_component_name` (Task 2), `_add_component_param` (pavlovia.py:282).
- Produces: `_add_loop_routine(routines, flow, question, conditions_filename) -> None`,
  called from `build_psyexp_xml`.

- [ ] **Step 1: Write the failing test**

```python
def _array_question():
    return {
        "code": "phq9", "description": "PHQ-9", "type": "array",
        "levels": {"0": "Not at all", "1": "Several days",
                   "2": "More than half", "3": "Nearly every day"},
        "items": {
            "1": {"Description": "Little interest or pleasure", "Order": 0},
            "2": {"Description": "Feeling down", "Order": 1},
        },
        "mandatory": True, "condition": None, "help": None,
        "position": {"Group": "phq", "GroupOrder": 0, "QuestionOrder": 0},
    }


def test_array_question_gets_loop_routine_and_flow_entries():
    xml_str = build_psyexp_xml("demo", [_array_question()], {})
    root = ET.fromstring(xml_str)

    loop_routine = root.find(".//Routines/Routine[@name='loop_phq9']")
    assert loop_routine is not None
    assert loop_routine.find("FormComponent") is not None

    flow = root.find("Flow")
    flow_children = list(flow)
    tags_and_names = [(c.tag, c.get("name")) for c in flow_children]
    assert ("LoopInitiator", "phq9_trials") in tags_and_names
    assert ("Routine", "loop_phq9") in tags_and_names
    assert ("LoopTerminator", "phq9_trials") in tags_and_names
    # Initiator must come before the routine, which must come before the terminator.
    init_idx = tags_and_names.index(("LoopInitiator", "phq9_trials"))
    routine_idx = tags_and_names.index(("Routine", "loop_phq9"))
    term_idx = tags_and_names.index(("LoopTerminator", "phq9_trials"))
    assert init_idx < routine_idx < term_idx
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: FAIL — no `loop_phq9` routine exists (loop-type questions are currently just
`continue`d past).

- [ ] **Step 3: Write minimal implementation**

Add after `create_textbox_component` (Task 2):

```python
def _add_loop_routine(
    routines: ET.Element,
    flow: ET.Element,
    question: Dict[str, Any],
    conditions_filename: Optional[str],
) -> None:
    """Add a Routine + Flow Loop for an array (Items) question.

    The Routine holds a Form driven by the per-row $conditions the loop
    supplies from conditions.csv (built by create_conditions_csv); the
    Flow gets a LoopInitiator/Routine/LoopTerminator triple so the trial
    handler actually iterates the subquestions instead of them being
    silently dropped.
    """
    safe_q_name = _safe_component_name(question["code"])
    routine_name = f"loop_{safe_q_name}"

    routine = ET.SubElement(routines, "Routine")
    routine.set("name", routine_name)

    form = ET.SubElement(routine, "FormComponent")
    form.set("name", f"form_{routine_name}")
    _add_component_param(form, "items", "$conditions")
    _add_component_param(form, "randomize", "False")

    loop_name = f"{safe_q_name}_trials"
    loop_init = ET.SubElement(flow, "LoopInitiator")
    loop_init.set("loopType", "TrialHandler")
    loop_init.set("name", loop_name)
    _add_component_param(loop_init, "nReps", "1")
    _add_component_param(loop_init, "loopType", "sequential")
    if conditions_filename:
        _add_component_param(loop_init, "conditions", conditions_filename)

    flow_item = ET.SubElement(flow, "Routine")
    flow_item.set("name", routine_name)

    loop_term = ET.SubElement(flow, "LoopTerminator")
    loop_term.set("name", loop_name)
```

`build_psyexp_xml` needs the conditions filename and needs to build `Flow` per-group
(interleaving loop entries) instead of in one flat pass at the end. Replace the whole
Flow-building section (pavlovia.py:257-272) and thread a `conditions_filename` parameter
through:

```python
def build_psyexp_xml(
    task_name: str,
    questions: List[Dict[str, Any]],
    prism_metadata: Dict[str, Any],
    conditions_filename: Optional[str] = None,
) -> str:
```

Replace the routine-building loop from Task 2 to also collect loop questions per group
(change the `elif component_type == "loop": continue` line to instead append to a
per-group list), then replace the flow section:

```python
        loop_questions: List[Dict[str, Any]] = []
        for q in group_questions:
            component_type = determine_component_type(q)
            ...  # (unchanged slider/textbox/form branches from Task 2)
            elif component_type == "loop":
                loop_questions.append(q)
            else:
                form_items.append(create_psychopy_form_item(q))
        group_loop_questions[group_name] = loop_questions
        ...  # (unchanged form_component block from Task 2)

    # Flow
    flow = ET.SubElement(root, "Flow")

    flow_item = ET.SubElement(flow, "Routine")
    flow_item.set("name", "welcome")

    for group_name in grouped_questions.keys():
        routine_name = f"group_{group_name.lower().replace(' ', '_')}"
        flow_item = ET.SubElement(flow, "Routine")
        flow_item.set("name", routine_name)
        for q in group_loop_questions.get(group_name, []):
            _add_loop_routine(routines, flow, q, conditions_filename)

    flow_item = ET.SubElement(flow, "Routine")
    flow_item.set("name", "thanks")
```

(`group_loop_questions: Dict[str, List[Dict[str, Any]]] = {}` initialized alongside
`grouped_questions` at the top of the function.)

Finally, update the one caller, `export_to_pavlovia` (pavlovia.py:401), to pass the
conditions filename it already computes:

```python
    psyexp_content = build_psyexp_xml(
        task_name,
        questions,
        prism_json,
        conditions_filename=conditions_path.name if conditions_path else None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "feat: wire array-question loops into pavlovia Flow instead of dropping them"
```

---

### Task 4: Condition → CodeComponent (if-statement) gating

Questions with a `condition` (Task 1) need a PsychoPy `CodeComponent` that skips the
routine's remaining components when the condition is false — the third promise in
`docs/PAVLOVIA_EXPORT.md`'s mapping table. PRISM's `showWhen`/`Relevance` strings
(`"sex == 'F'"`, `and`/`or`) are already valid Python boolean expressions over question
codes, so this needs name-mapping, not a language translation (unlike
`_build_relevance_equation` in `limesurvey_exporter.py`, which targets LimeSurvey's
Expression Manager syntax — different target language, not reusable here).

**Files:**
- Modify: `src/converters/pavlovia.py` (`build_psyexp_xml`)
- Test: `tests/test_pavlovia_exporter.py`

**Interfaces:**
- Produces: `_build_condition_code_component(question, safe_q_name) ->
  Optional[ET.Element]`, called from the per-question loop added in Task 2/3.

- [ ] **Step 1: Write the failing test**

```python
def test_conditional_question_gets_code_component_guard():
    q = _sample_questions()[0]
    q["condition"] = "sex == 'F'"
    xml_str = build_psyexp_xml("demo", [q], {})
    root = ET.fromstring(xml_str)
    code_components = root.findall(".//CodeComponent")
    assert len(code_components) == 1
    begin_routine_param = code_components[0].find("./Param[@name='Begin Routine']")
    assert begin_routine_param is not None
    assert "sex == 'F'" in begin_routine_param.get("val")
    assert "continueRoutine = False" in begin_routine_param.get("val")


def test_unconditional_question_gets_no_code_component():
    xml_str = build_psyexp_xml("demo", _sample_questions(), {})
    root = ET.fromstring(xml_str)
    assert root.findall(".//CodeComponent") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: FAIL — no `CodeComponent` is ever emitted today.

- [ ] **Step 3: Write minimal implementation**

Add after `_add_loop_routine` (Task 3):

```python
def _build_condition_code_component(
    question: Dict[str, Any], safe_q_name: str
) -> Optional[ET.Element]:
    """Build a CodeComponent that skips the routine when `condition` is false.

    PRISM's ConditionalDisplay.showWhen / Relevance strings are already
    Python-boolean-expression-shaped ("sex == 'F'", and/or), so this only
    needs to wrap the expression, not translate its syntax.
    """
    condition = question.get("condition")
    if not condition:
        return None

    code = ET.Element("CodeComponent")
    code.set("name", f"code_{safe_q_name}_condition")
    begin_routine = (
        f"if not ({condition}):\n"
        f"    continueRoutine = False"
    )
    param = ET.SubElement(code, "Param")
    param.set("name", "Begin Routine")
    param.set("val", begin_routine)
    param.set("valType", "extendedCode")
    return code
```

In the per-question loop (Task 2/3), after handling `component_type`, append the guard
regardless of type:

```python
            condition_component = _build_condition_code_component(q, safe_q_name)
            if condition_component is not None:
                routine.append(condition_component)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "feat: gate conditional pavlovia questions with a CodeComponent"
```

---

### Task 5: Implement `import_from_pavlovia`

Currently a stub that prints "not yet implemented" and returns `None`. Implement the
reverse mapping promised by the docstring: read a Pavlovia-downloaded CSV, map its
columns back to PRISM question codes using the original PRISM JSON, and write a
PRISM-compatible TSV.

**Files:**
- Modify: `src/converters/pavlovia.py` (`import_from_pavlovia`)
- Test: `tests/test_pavlovia_exporter.py`

**Interfaces:**
- Consumes: `load_prism_json` (pavlovia.py:36), `extract_questions` (Task 1's version).
- Produces: `import_from_pavlovia(pavlovia_csv, prism_json, output_tsv=None) ->
  Optional[Path]` — same signature as today, now actually implemented.

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd
from src.converters.pavlovia import import_from_pavlovia


def test_import_from_pavlovia_maps_columns_to_prism_codes(tmp_path):
    prism_path = tmp_path / "task-demo_beh.json"
    prism_path.write_text(
        '{"mood_1": {"Description": "Sadness", "QuestionType": "text"}, '
        '"comments": {"Description": "Notes", "QuestionType": "text"}}',
        encoding="utf-8",
    )

    pavlovia_csv = tmp_path / "pavlovia_data.csv"
    pd.DataFrame(
        [{"slider_mood_1.response": "2", "textbox_comments.text": "fine",
          "participant": "sub-01", "session": "001"}]
    ).to_csv(pavlovia_csv, index=False)

    output_tsv = tmp_path / "out.tsv"
    result = import_from_pavlovia(pavlovia_csv, prism_path, output_tsv)

    assert result == output_tsv
    df = pd.read_csv(output_tsv, sep="\t")
    assert list(df["mood_1"]) == ["2"]
    assert list(df["comments"]) == ["fine"]
    assert list(df["participant_id"]) == ["sub-01"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: FAIL — `import_from_pavlovia` returns `None` unconditionally today.

- [ ] **Step 3: Write minimal implementation**

Replace `import_from_pavlovia` (pavlovia.py:414-435):

```python
def import_from_pavlovia(
    pavlovia_csv: Path,
    prism_json: Path,
    output_tsv: Optional[Path] = None,
) -> Optional[Path]:
    """Import Pavlovia data back to PRISM format.

    Maps Pavlovia's per-component column names (e.g. "slider_mood_1.response",
    "textbox_comments.text") back to PRISM question codes using the
    slider_/textbox_/form_ + _safe_component_name() naming this module's own
    export side uses, so round-tripping an export this module produced works
    without a separate mapping file.

    Args:
        pavlovia_csv: CSV file downloaded from Pavlovia
        prism_json: Original PRISM survey JSON (for column mapping)
        output_tsv: Output TSV path (default: auto-generated)

    Returns:
        Path to created TSV file, or None if no matching columns were found.
    """
    prism_data = load_prism_json(prism_json)
    questions = extract_questions(prism_data)
    code_by_safe_name = {_safe_component_name(q["code"]): q["code"] for q in questions}

    df = pd.read_csv(pavlovia_csv)

    column_map: Dict[str, str] = {}
    for column in df.columns:
        prefix, _, suffix = column.partition(".")
        for known_prefix in ("slider_", "textbox_", "form_"):
            if prefix.startswith(known_prefix):
                safe_name = prefix[len(known_prefix):]
                if safe_name in code_by_safe_name:
                    column_map[column] = code_by_safe_name[safe_name]
                break

    if column_map:
        column_map.setdefault("participant", "participant_id")
        column_map.setdefault("session", "session_id")

    if not column_map:
        print("⚠️  No matching Pavlovia columns found for this PRISM survey")
        return None

    out_df = df[list(column_map.keys())].rename(columns=column_map)

    if output_tsv is None:
        output_tsv = pavlovia_csv.with_suffix(".tsv")
    out_df.to_csv(output_tsv, sep="\t", index=False)
    print(f"✅ Imported Pavlovia data: {output_tsv}")
    return output_tsv
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "feat: implement Pavlovia CSV to PRISM TSV import"
```

---

### Task 6: CLI wiring — `survey export-pavlovia`

Mirror the existing `export-lss` wiring exactly (`parser.py` → `dispatch.py` →
`entrypoint.py` → `cli/commands/survey.py`).

**Files:**
- Modify: `app/src/cli/parser.py` (new subparser, after `parser_survey_export_lss_customized`
  around line 1341+)
- Modify: `app/src/cli/dispatch.py` (new `elif` branch near line 66-69)
- Modify: `app/src/cli/commands/survey.py` (new `cmd_survey_export_pavlovia`, alongside
  `cmd_survey_export_lss` at line 739)
- Modify: `app/src/cli/entrypoint.py` (import + `handlers` dict entry near line 65-117)
- Test: `tests/test_cli_survey_export_pavlovia.py` (new file)

**Interfaces:**
- Consumes: `export_to_pavlovia(json_path, output_dir=None, experiment_name=None) ->
  Path` (pavlovia.py:356, unchanged signature).
- Produces: CLI action `survey export-pavlovia`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_survey_export_pavlovia.py
"""CLI wiring test for `survey export-pavlovia`, mirroring
tests/test_cli_survey_export_commands.py's pattern for export-lss."""
import json
import subprocess
import sys
from pathlib import Path


def test_cli_export_pavlovia_creates_psyexp(tmp_path):
    prism_json = tmp_path / "task-demo_beh.json"
    prism_json.write_text(
        json.dumps({"q1": {"Description": "Q1", "QuestionType": "text"}}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    result = subprocess.run(
        [sys.executable, "-m", "src.cli.entrypoint", "survey", "export-pavlovia",
         str(prism_json), "--output", str(output_dir)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "demo.psyexp").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_survey_export_pavlovia.py -v`
Expected: FAIL — `export-pavlovia` is not a recognized `survey` action (argparse error).

- [ ] **Step 3: Write minimal implementation**

In `app/src/cli/parser.py`, after the `parser_survey_export_lss_customized` block:

```python
    parser_survey_export_pavlovia = survey_subparsers.add_parser(
        "export-pavlovia",
        help="Export a PRISM survey template JSON file to a Pavlovia/PsychoPy "
        "experiment (.psyexp + conditions.csv). Matches the Studio GUI's "
        "Survey Generator 'Quick Export' action when Pavlovia is selected.",
    )
    parser_survey_export_pavlovia.add_argument(
        "json_path", help="Path to a PRISM survey template JSON file"
    )
    parser_survey_export_pavlovia.add_argument(
        "--output", required=True, help="Output directory for the experiment files"
    )
    parser_survey_export_pavlovia.add_argument(
        "--experiment-name", default=None, help="Override the experiment name"
    )
```

In `app/src/cli/dispatch.py`, after the `export-lss-customized` branch:

```python
        elif args.action == "export-pavlovia":
            handlers["survey_export_pavlovia"](args)
```

In `app/src/cli/commands/survey.py`, near `cmd_survey_export_lss`:

```python
def cmd_survey_export_pavlovia(args) -> None:
    """Export a PRISM survey template JSON file to a Pavlovia/PsychoPy
    experiment — the CLI equivalent of the Studio GUI's Survey Generator
    "Quick Export" action when Pavlovia is the selected tool
    (src.converters.pavlovia.export_to_pavlovia)."""
    from src.converters.pavlovia import export_to_pavlovia

    json_path = Path(args.json_path).resolve()
    if not json_path.exists():
        print(f"Error: file not found: {json_path}")
        sys.exit(1)

    output_dir = Path(args.output).resolve()

    try:
        export_to_pavlovia(json_path, output_dir, args.experiment_name)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)
```

Add `cmd_survey_export_pavlovia` to that file's imports in `app/src/cli/entrypoint.py`
(alongside `cmd_survey_export_lss`) and to the `handlers` dict:

```python
            "survey_export_pavlovia": cmd_survey_export_pavlovia,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_survey_export_pavlovia.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/src/cli/parser.py app/src/cli/dispatch.py app/src/cli/commands/survey.py \
        app/src/cli/entrypoint.py tests/test_cli_survey_export_pavlovia.py
git commit -m "feat: add survey export-pavlovia CLI command"
```

---

### Task 7: Web backend wiring — `/api/generate-pavlovia`

Unlike LSS (single file), a Pavlovia export produces a directory (`.psyexp` +
`conditions.csv` + `README.md`), so the endpoint zips the output directory with stdlib
`zipfile` before sending it — same idea as the existing `template-export` ZIP download,
no new dependency.

**Files:**
- Modify: `app/src/web/blueprints/tools_generation_handlers.py` (new handler, alongside
  `handle_generate_lss_endpoint` at line 40)
- Modify: `app/src/web/blueprints/tools.py` (new route, alongside line 1965's
  `generate-lss` route; add the handler to the import block at line 63)
- Test: `tests/test_tools_generation_handlers.py` (extend existing file)

**Interfaces:**
- Consumes: `export_to_pavlovia` (pavlovia.py:356).
- Produces: Flask route `POST /api/generate-pavlovia`, request body
  `{"files": [{"path": ...}], "experiment_name": <optional str>}`, response: a
  `.zip` file download.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_tools_generation_handlers.py
def test_handle_generate_pavlovia_endpoint_returns_zip(app_client, tmp_path):
    prism_json = tmp_path / "task-demo_beh.json"
    prism_json.write_text(
        '{"q1": {"Description": "Q1", "QuestionType": "text"}}', encoding="utf-8"
    )

    response = app_client.post(
        "/api/generate-pavlovia",
        json={"files": [{"path": str(prism_json)}]},
    )

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
```

(Follow whatever `app_client` fixture `tests/test_tools_generation_handlers.py` already
uses for `handle_generate_lss_endpoint`'s tests — reuse it, don't add a second fixture.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools_generation_handlers.py -v -k pavlovia`
Expected: FAIL — 404, route doesn't exist yet.

- [ ] **Step 3: Write minimal implementation**

In `app/src/web/blueprints/tools_generation_handlers.py`, after
`handle_generate_lss_endpoint`:

```python
def handle_generate_pavlovia_endpoint():
    """Generate a Pavlovia/PsychoPy experiment .zip from selected PRISM JSON files."""
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

Add `import zipfile` to the file's import block (alongside the existing `os`, `sys`,
`tempfile`, `Path` imports at the top).

In `app/src/web/blueprints/tools.py`, add `handle_generate_pavlovia_endpoint` to the
import block at line 63, and after the `generate-lss` route (line 1965-1968):

```python
@tools_bp.route("/api/generate-pavlovia", methods=["POST"])
def generate_pavlovia_endpoint():
    """Generate Pavlovia/PsychoPy experiment from selected JSON files."""
    return handle_generate_pavlovia_endpoint()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools_generation_handlers.py -v -k pavlovia`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/src/web/blueprints/tools_generation_handlers.py app/src/web/blueprints/tools.py \
        tests/test_tools_generation_handlers.py
git commit -m "feat: add /api/generate-pavlovia endpoint returning a zipped experiment"
```

---

### Task 8: Studio GUI wiring

The Survey Generator's tool selector already has the extensibility point for this — it
has commented-out `redcap`/`qualtrics` entries in `toolConfig`
(`app/static/js/survey-generator.js:65-68`) but the `<select>` in the template only
offers `limesurvey` (`app/templates/survey_generator.html:44`). Add the real `pavlovia`
entry and option, and handle the `.zip` response (LSS handling assumes a single-file
blob already — the existing `downloadBlobObj(blob, ...)` call at line 655 works
unchanged for a zip blob, since it's just bytes + filename).

**Files:**
- Modify: `app/templates/survey_generator.html:43-45`
- Modify: `app/static/js/survey-generator.js:65`

- [ ] **Step 1: Write the failing test**

This is UI wiring with no existing JS test harness in this repo for
`survey-generator.js` (confirm: `grep -rn "survey-generator" tests/` — if a JS test
runner exists, add one there; otherwise this step is manual verification, per this
plan's Global Constraints note on what can't be automated in this environment).

Manual check: open Survey Generator in the Studio GUI, confirm the tool dropdown lists
"Pavlovia/PsychoPy", and confirm the export button downloads a `.zip`.

- [ ] **Step 2: N/A — no automated test for this step, see Step 1**

- [ ] **Step 3: Write minimal implementation**

In `app/templates/survey_generator.html`, change:
```html
                    <select class="form-select form-select-sm" id="targetToolSelect" style="width:auto;">
                        <option value="limesurvey">LimeSurvey</option>
                    </select>
```
to:
```html
                    <select class="form-select form-select-sm" id="targetToolSelect" style="width:auto;">
                        <option value="limesurvey">LimeSurvey</option>
                        <option value="pavlovia">Pavlovia/PsychoPy</option>
                    </select>
```

In `app/static/js/survey-generator.js`, change line 65 from:
```js
        limesurvey: { label: 'LimeSurvey', exportEndpoint: '/api/generate-lss', fileExt: '.lss', optionsClass: 'tool-options-limesurvey' },
```
to add a sibling entry (keep the commented redcap/qualtrics placeholders as-is):
```js
        limesurvey: { label: 'LimeSurvey', exportEndpoint: '/api/generate-lss', fileExt: '.lss', optionsClass: 'tool-options-limesurvey' },
        pavlovia: { label: 'Pavlovia/PsychoPy', exportEndpoint: '/api/generate-pavlovia', fileExt: '.zip', optionsClass: 'tool-options-pavlovia' },
```

No LimeSurvey-specific UI (language/version selectors, `tool-options-limesurvey`) applies
to Pavlovia — leave `tool-options-pavlovia` with no matching DOM block, so nothing extra
renders for it (the existing `getToolConfig()`/class-toggle logic at lines 92-98 already
hides/shows purely by class match, so an unmatched class is a no-op, not an error).

- [ ] **Step 4: Manual verification**

Run the app (`run` skill or existing dev-server steps), open Survey Generator, select
"Pavlovia/PsychoPy" from the dropdown, click Quick Export, confirm a `.zip` downloads and
contains `<name>.psyexp`, `conditions.csv` (if the survey has array questions), and
`README.md`.

- [ ] **Step 5: Commit**

```bash
git add app/templates/survey_generator.html app/static/js/survey-generator.js
git commit -m "feat: add Pavlovia/PsychoPy option to Survey Generator tool selector"
```

---

### Task 9: End-to-end regression test + manual PsychoPy verification note

Tie Tasks 1-5 together with one integration test that exercises the full
`export_to_pavlovia` path against a realistic multi-question, multi-type PRISM survey
(slider + textbox + array + conditional questions all present at once), matching the
style of `tests/test_lsa_import_integration.py`'s `generate_lss` integration tests.

**Files:**
- Modify: `tests/test_pavlovia_exporter.py`

- [ ] **Step 1: Write the failing test**

```python
from src.converters.pavlovia import export_to_pavlovia
import xml.etree.ElementTree as ET


def test_export_to_pavlovia_end_to_end(tmp_path):
    prism_json = tmp_path / "task-phq_beh.json"
    prism_json.write_text(json.dumps({
        "Study": {"TaskName": "phq"},
        "mood_1": {
            "Description": "Sadness", "QuestionType": "text",
            "Levels": {"0": "Not at all", "1": "A little",
                       "2": "Moderately", "3": "Extremely"},
            "Position": {"Group": "mood", "GroupOrder": 0, "QuestionOrder": 0},
        },
        "comments": {
            "Description": "Anything else?", "QuestionType": "long_free_text",
            "Position": {"Group": "mood", "GroupOrder": 0, "QuestionOrder": 1},
        },
        "phq9": {
            "Description": "PHQ-9", "QuestionType": "array",
            "Levels": {"0": "Not at all", "1": "Several days",
                       "2": "More than half", "3": "Nearly every day"},
            "Items": {"1": {"Description": "Little interest", "Order": 0}},
            "Position": {"Group": "phq", "GroupOrder": 1, "QuestionOrder": 0},
        },
        "pregnant": {
            "Description": "Pregnant?", "QuestionType": "text",
            "ConditionalDisplay": {"showWhen": "mood_1 == '3'"},
            "Position": {"Group": "mood", "GroupOrder": 0, "QuestionOrder": 2},
        },
    }), encoding="utf-8")

    output_dir = tmp_path / "out"
    psyexp_path = export_to_pavlovia(prism_json, output_dir)

    assert psyexp_path.exists()
    assert (output_dir / "conditions.csv").exists()
    assert (output_dir / "README.md").exists()

    root = ET.fromstring(psyexp_path.read_text(encoding="utf-8"))
    assert root.findall(".//SliderComponent")
    assert root.findall(".//TextboxComponent")
    assert root.findall(".//CodeComponent")
    assert root.find(".//Routines/Routine[@name='loop_phq9']") is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pavlovia_exporter.py -v -k end_to_end`
Expected: FAIL if any of Tasks 1-5 is incomplete — this is the integration checkpoint.

- [ ] **Step 3: No new implementation** — this test should pass once Tasks 1-5 are
  correctly merged. If it fails after all five are done, that's a real integration bug
  (e.g. a param name mismatch between two tasks' code) — fix it here rather than
  papering over it in the unit tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Manual verification (cannot be automated in this environment)**

Install PsychoPy locally (`pip install psychopy`, or use the PsychoPy Standalone app),
open the generated `.psyexp` in Builder, and confirm it loads without a schema error.
This plan's tests only prove the XML is well-formed and structurally matches the
documented mapping table — they do not prove Builder-compatibility. Record the result
(pass/fail + PsychoPy version tested) in `docs/PAVLOVIA_EXPORT.md` once done, and file a
follow-up if it doesn't load cleanly — don't mark this feature "done" in any user-facing
doc until this step has actually been run once by a human with PsychoPy installed.

- [ ] **Step 6: Commit**

```bash
git add tests/test_pavlovia_exporter.py
git commit -m "test: add pavlovia exporter end-to-end integration test"
```

---

## Self-Review

**Spec coverage:** the four gaps identified in the assessment are each covered — dead
`determine_component_type` (Task 2), dropped array `Items` (Task 3), unused `Condition`
(Tasks 1 + 4), stub `import_from_pavlovia` (Task 5). The "unwired" gap is covered by
Tasks 6-8 (CLI, backend, frontend). Task 9 is the integration checkpoint plus the
explicit call-out that PsychoPy-Builder-loadability itself is outside what this
environment can verify automatically.

**Placeholder scan:** no TBD/"add error handling"/"similar to Task N" — every step has
concrete code. Task 8 Step 1/2 is the one deliberate exception (no automated test
exists for this repo's plain JS), and it's explicit about why and what to do instead
(manual check), not a silently skipped step.

**Type/name consistency:** `_safe_component_name` (Task 2) is the single naming
authority component names and Task 5's import both key off — Task 5 reads
`slider_`/`textbox_`/`form_` prefixes that Tasks 2/3 are the ones actually emitting, so
the round-trip is internally consistent. `conditions_filename` param threaded through
`build_psyexp_xml` (Task 3) is passed from `export_to_pavlovia` (also Task 3) using the
same `conditions_path.name` the function already computes earlier in its body — no
new/renamed conditions-file variable introduced.
