# Pavlovia Customizer Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Pavlovia/PsychoPy a real export target on the Survey Customizer screen ("Customize Export"), combining several customized questionnaires into one PsychoPy experiment (one routine per questionnaire) the same way LimeSurvey export already combines them into one `.lss`.

**Architecture:** Generalize the existing single-file `build_psyexp_xml` into a multi-routine `build_psyexp_xml_grouped` (old function becomes a 1-line wrapper, zero behavior change for current callers). Add a customizer-group question extractor and a new `generate_pavlovia_from_customization` entry point in `src/converters/pavlovia.py`, parallel to `src/limesurvey_exporter.py::generate_lss_from_customization`. Wire it into the existing `/api/survey-customizer/export` handler as a second branch, and add the missing UI option + LimeSurvey-only-options visibility toggle.

**Tech Stack:** Python (Flask backend, `xml.etree.ElementTree` for `.psyexp` XML, `pandas` for `conditions.csv`), vanilla JS + Bootstrap (frontend), pytest.

**Spec:** `docs/superpowers/specs/2026-09-09-pavlovia-customizer-export-design.md`

## Global Constraints

- `build_psyexp_xml(task_name, questions, prism_metadata)` must keep its exact current signature and output for every existing caller/test — it becomes a thin wrapper, not a breaking change.
- Pavlovia export stays single-language (per `export_to_pavlovia`'s existing docstring) — the customizer path inherits this, no multi-language UI is added.
- The CLI (`survey export-pavlovia`) and the Survey Export screen's own `/api/generate-pavlovia` endpoint are out of scope — do not modify `tools_generation_handlers.py` or the CLI.
- No REDCap/Qualtrics work — the commented-out placeholder options in `survey_customizer.html` stay as-is.
- Dual-tree drift (per repo `CLAUDE.md`): `src/converters/pavlovia.py` has no `app/src/converters/pavlovia.py` counterpart, and `tools_survey_customizer_handlers.py`/`survey_customizer.html`/`survey-customizer.js` live only under `app/`. No mirrored-file risk for any file this plan touches — no drift check needed mid-implementation.

---

## Task 1: Generalize `build_psyexp_xml` into a multi-routine builder

**Files:**
- Modify: `src/converters/pavlovia.py:16` (typing import), `src/converters/pavlovia.py:275-399` (`build_psyexp_xml`)
- Test: `tests/test_pavlovia_exporter.py`

**Interfaces:**
- Produces: `build_psyexp_xml_grouped(task_name: str, routine_groups: List[Tuple[str, List[Dict[str, Any]]]], prism_metadata: Dict[str, Any]) -> str` — one `Routine` per `(routine_name, questions)` pair in `routine_groups`, inserted into `Flow` in that order, bracketed by fixed `welcome`/`thanks` routines.
- Produces (unchanged signature): `build_psyexp_xml(task_name: str, questions: List[Dict[str, Any]], prism_metadata: Dict[str, Any]) -> str` — now `return build_psyexp_xml_grouped(task_name, [("questions", questions)], prism_metadata)`.

- [ ] **Step 1: Write the failing test for multi-routine output**

Add to `tests/test_pavlovia_exporter.py` (add `build_psyexp_xml_grouped` to the existing import block at the top, and add `Tuple`-shaped sample data inline):

```python
def test_build_psyexp_xml_grouped_one_routine_per_group():
    from src.converters.pavlovia import build_psyexp_xml_grouped

    group_a = [{"code": "q1", "description": "Q1", "levels": {}, "mandatory": True, "condition": None}]
    group_b = [{"code": "q2", "description": "Q2", "levels": {}, "mandatory": True, "condition": None}]

    xml_str = build_psyexp_xml_grouped("combo", [("groupA", group_a), ("groupB", group_b)], {})
    root = ET.fromstring(xml_str)

    routines_section = root.find("Routines")
    routine_names = [r.get("name") for r in routines_section.findall("Routine")]
    assert routine_names == ["welcome", "groupA", "groupB", "thanks"]

    flow = root.find("Flow")
    flow_names = [r.get("name") for r in flow.findall("Routine")]
    assert flow_names == ["welcome", "groupA", "groupB", "thanks"]


def test_build_psyexp_xml_wraps_grouped_with_single_questions_routine():
    from src.converters.pavlovia import build_psyexp_xml_grouped

    questions = _sample_questions()
    assert build_psyexp_xml("recovery", questions, {}) == build_psyexp_xml_grouped(
        "recovery", [("questions", questions)], {}
    )
```

`_sample_questions()` already exists in this test file (used by the existing `build_psyexp_xml` tests around line 220) — reuse it, don't redefine it.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `pytest tests/test_pavlovia_exporter.py -k "grouped" -v`
Expected: FAIL — `ImportError`/`AttributeError`, `build_psyexp_xml_grouped` does not exist yet.

- [ ] **Step 3: Implement `build_psyexp_xml_grouped` and the wrapper**

In `src/converters/pavlovia.py`, change the typing import at line 16:

```python
from typing import Dict, List, Any, Optional, Tuple
```

Replace the whole `build_psyexp_xml` function (lines 275-399) with:

```python
def build_psyexp_xml_grouped(
    task_name: str,
    routine_groups: List[Tuple[str, List[Dict[str, Any]]]],
    prism_metadata: Dict[str, Any],
) -> str:
    """Build the PsychoPy .psyexp XML structure from one or more question routines.

    This creates a minimal but functional experiment with:
    - Welcome screen
    - One question routine per (routine_name, questions) pair in
      routine_groups, each holding a real component per question
      (SliderComponent/TextboxComponent/shared FormComponent, per
      determine_component_type), plus an optional CodeComponent for a
      non-null condition -- this only surfaces the PRISM condition text as a
      TODO comment for a researcher to translate manually; it does not gate
      visibility automatically
    - Thank you screen
    - Flow connecting all routines, in routine_groups order
    """

    root = ET.Element("PsychoPy2experiment")
    root.set("version", PSYCHOPY_VERSION)
    root.set("encoding", "utf-8")

    # Settings
    settings = ET.SubElement(root, "Settings")
    for key, value in EXPERIMENT_SETTINGS.items():
        param = ET.SubElement(settings, "Param")
        param.set("name", key)
        param.set("val", str(value))

    # Routines section
    routines = ET.SubElement(root, "Routines")

    # 1. Welcome routine
    welcome_routine = ET.SubElement(routines, "Routine")
    welcome_routine.set("name", "welcome")

    welcome_text = ET.SubElement(welcome_routine, "TextComponent")
    welcome_text.set("name", "welcome_text")
    _add_component_param(welcome_text, "text", f"Welcome to {task_name}")
    _add_component_param(welcome_text, "pos", "[0, 0]")
    _add_component_param(welcome_text, "height", "0.05")

    welcome_key = ET.SubElement(welcome_routine, "KeyboardComponent")
    welcome_key.set("name", "welcome_key")
    _add_component_param(welcome_key, "keys", "['space']")
    _add_component_param(welcome_key, "text", "Press SPACE to continue")

    # 2. One question routine per routine_groups entry
    for routine_name, questions in routine_groups:
        routine = ET.SubElement(routines, "Routine")
        routine.set("name", routine_name)

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
                    "# TODO: this question is conditionally displayed in PRISM:\n"
                    f"# {q['condition']}\n"
                    "# Translate this into PsychoPy/JS logic to gate visibility.\n"
                    f"{safe_name}_visible = True",
                )

        if form_items:
            form_component = ET.SubElement(routine, "FormComponent")
            form_component.set("name", f"form_{routine_name}")
            _add_component_param(form_component, "items", str(form_items))
            _add_component_param(form_component, "randomize", "False")

    # 3. Thank you routine
    thanks_routine = ET.SubElement(routines, "Routine")
    thanks_routine.set("name", "thanks")

    thanks_text = ET.SubElement(thanks_routine, "TextComponent")
    thanks_text.set("name", "thanks_text")
    _add_component_param(thanks_text, "text", "Thank you for participating!")
    _add_component_param(thanks_text, "pos", "[0, 0]")
    _add_component_param(thanks_text, "duration", "2.0")

    # Flow
    flow = ET.SubElement(root, "Flow")

    flow_item = ET.SubElement(flow, "Routine")
    flow_item.set("name", "welcome")

    for routine_name, _questions in routine_groups:
        flow_item = ET.SubElement(flow, "Routine")
        flow_item.set("name", routine_name)

    flow_item = ET.SubElement(flow, "Routine")
    flow_item.set("name", "thanks")

    # Convert to pretty XML string
    xml_str = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(xml_str)  # nosec B318 - xml_str is self-generated above, not untrusted input
    pretty_xml = dom.toprettyxml(indent="  ")

    return pretty_xml


def build_psyexp_xml(
    task_name: str,
    questions: List[Dict[str, Any]],
    prism_metadata: Dict[str, Any],
) -> str:
    """Build a single-routine .psyexp -- the CLI/single-file export path.

    Thin wrapper over build_psyexp_xml_grouped with one routine named
    "questions", preserving this function's original single-routine output.
    """
    return build_psyexp_xml_grouped(task_name, [("questions", questions)], prism_metadata)
```

Note: the `FormComponent` name changes from the old hardcoded `"form_questions"` to `f"form_{routine_name}"` — for the wrapper's single `"questions"` routine this evaluates to the identical `"form_questions"` string, so existing single-file output is unaffected. For multiple groups it prevents two routines from emitting colliding `FormComponent` names.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `pytest tests/test_pavlovia_exporter.py -k "grouped" -v`
Expected: PASS

- [ ] **Step 5: Run the full existing test file to confirm no regressions**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: all tests PASS, including the pre-existing `test_build_psyexp_xml_*` and `test_export_to_pavlovia_*` tests (they exercise `build_psyexp_xml`/`export_to_pavlovia` unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "$(cat <<'EOF'
refactor: generalize build_psyexp_xml into a multi-routine builder

build_psyexp_xml_grouped builds one PsychoPy Routine per (name,
questions) pair; build_psyexp_xml becomes a 1-line single-routine
wrapper over it with identical output, laying the groundwork for a
Pavlovia export that combines several customized questionnaires.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Extract questions from a Survey Customizer group

**Files:**
- Modify: `src/converters/pavlovia.py` (add after `extract_questions`, i.e. after line 167)
- Test: `tests/test_pavlovia_exporter.py`

**Interfaces:**
- Consumes: `_resolve_text(value, language)`, `_extract_condition(value)` (both already defined earlier in `pavlovia.py`).
- Produces: `extract_questions_from_customized_group(group: Dict[str, Any], language: Optional[str] = None) -> List[Dict[str, Any]]` — same per-question dict shape as `extract_questions` (`code`, `description`, `levels`, `raw_levels`, `data_type`, `scale_type`, `min_value`, `max_value`, `mandatory`, `condition`, `help`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pavlovia_exporter.py` (add `extract_questions_from_customized_group` to the top import block):

```python
def _sample_group():
    return {
        "id": "g1",
        "name": "Sample Group",
        "questions": [
            {
                "questionCode": "q2",
                "displayOrder": 1,
                "enabled": True,
                "mandatory": True,
                "originalData": {"Description": "Second question", "DataType": "string"},
            },
            {
                "questionCode": "q1",
                "displayOrder": 0,
                "enabled": True,
                "mandatory": False,
                "originalData": {
                    "Description": "First question",
                    "DataType": "integer",
                    "Levels": {"1": "Yes", "2": "No"},
                    "Mandatory": True,
                },
            },
            {
                "questionCode": "q3",
                "displayOrder": 2,
                "enabled": False,
                "mandatory": True,
                "originalData": {"Description": "Disabled question"},
            },
        ],
    }


def test_extract_questions_from_customized_group_orders_and_filters():
    questions = extract_questions_from_customized_group(_sample_group())
    assert [q["code"] for q in questions] == ["q1", "q2"]


def test_extract_questions_from_customized_group_honors_mandatory_override():
    questions = extract_questions_from_customized_group(_sample_group())
    by_code = {q["code"]: q for q in questions}
    # q1's originalData says Mandatory=True, but the customizer overrode it to False
    assert by_code["q1"]["mandatory"] is False


def test_extract_questions_from_customized_group_resolves_description_and_levels():
    questions = extract_questions_from_customized_group(_sample_group())
    by_code = {q["code"]: q for q in questions}
    assert by_code["q1"]["description"] == "First question"
    assert by_code["q1"]["levels"] == {"1": "Yes", "2": "No"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_pavlovia_exporter.py -k "customized_group" -v`
Expected: FAIL — `extract_questions_from_customized_group` not defined.

- [ ] **Step 3: Implement the function**

In `src/converters/pavlovia.py`, add immediately after `extract_questions` (after line 167):

```python
def extract_questions_from_customized_group(
    group: Dict[str, Any], language: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Extract question data from one Survey Customizer group.

    Mirrors extract_questions()'s output shape, but reads from the
    customizer's `group["questions"]` list instead of a raw PRISM JSON
    file: filters to `enabled` questions, orders by `displayOrder`, and
    takes `mandatory` from the customizer's own field (a UI override) with
    each question's stored `originalData` as the fallback -- matching how
    the customizer's own LimeSurvey export already treats originalData as
    the source of truth for description/levels.
    """
    resolved_language = language or "en"
    ordered = sorted(
        (q for q in group.get("questions", []) if q.get("enabled", True)),
        key=lambda q: q.get("displayOrder", 0),
    )

    questions = []
    for q in ordered:
        original = q.get("originalData") or {}
        raw_levels = original.get("Levels") if isinstance(original.get("Levels"), dict) else {}
        flat_levels = {
            level_key: _resolve_text(level_value, resolved_language)
            for level_key, level_value in raw_levels.items()
        }

        questions.append(
            {
                "code": q.get("questionCode", ""),
                "description": _resolve_text(
                    original.get("Description", q.get("description", "")), resolved_language
                ),
                "levels": flat_levels,
                "raw_levels": raw_levels,
                "data_type": original.get("DataType", q.get("dataType", "string")),
                "scale_type": original.get("ScaleType"),
                "min_value": original.get("MinValue", q.get("minValue")),
                "max_value": original.get("MaxValue", q.get("maxValue")),
                "mandatory": q.get("mandatory", original.get("Mandatory", True)),
                "condition": _extract_condition(original),
                "help": original.get("HelpText", q.get("help") or None),
            }
        )

    return questions
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pavlovia_exporter.py -k "customized_group" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "$(cat <<'EOF'
feat: extract Pavlovia questions from a Survey Customizer group

extract_questions_from_customized_group reads the browser's
already-filtered/reordered group model instead of a raw PRISM JSON
file, honoring the customizer's own mandatory-flag override.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `generate_pavlovia_from_customization` end-to-end

**Files:**
- Modify: `src/converters/pavlovia.py` (extend `create_conditions_csv`, add `_unique_routine_name` and `generate_pavlovia_from_customization`)
- Test: `tests/test_pavlovia_exporter.py`

**Interfaces:**
- Consumes: `_safe_component_name`, `extract_questions_from_customized_group` (Task 2), `build_psyexp_xml_grouped` (Task 1), `create_readme(output_dir, task_name)` (existing).
- Produces: `generate_pavlovia_from_customization(groups: List[Dict[str, Any]], output_dir: Path, experiment_name: str, language: Optional[str] = None) -> Path` — returns the written `.psyexp` path; raises `ValueError` if every group is empty after filtering.
- Produces: `create_conditions_csv(questions, output_dir, routine_labels: Optional[List[str]] = None) -> Optional[Path]` — unchanged shape when `routine_labels` is omitted; adds a `routine` column when given.

- [ ] **Step 1: Write the failing test for the `create_conditions_csv` extension**

Add to `tests/test_pavlovia_exporter.py`:

```python
def test_create_conditions_csv_adds_routine_column_when_labels_given(tmp_path):
    questions = [
        {"code": "q1", "description": "Q1", "levels": {}},
        {"code": "q2", "description": "Q2", "levels": {}},
    ]
    csv_path = create_conditions_csv(questions, tmp_path, routine_labels=["groupA", "groupB"])
    df = pd.read_csv(csv_path)
    assert list(df["routine"]) == ["groupA", "groupB"]


def test_create_conditions_csv_unchanged_when_routine_labels_omitted(tmp_path):
    questions = [{"code": "q1", "description": "Q1", "levels": {}}]
    csv_path = create_conditions_csv(questions, tmp_path)
    df = pd.read_csv(csv_path)
    assert "routine" not in df.columns
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_pavlovia_exporter.py -k "routine_column or routine_labels_omitted" -v`
Expected: FAIL — `create_conditions_csv() got an unexpected keyword argument 'routine_labels'`

- [ ] **Step 3: Extend `create_conditions_csv`**

Replace `create_conditions_csv` (lines 226-252) with:

```python
def create_conditions_csv(
    questions: List[Dict[str, Any]],
    output_dir: Path,
    routine_labels: Optional[List[str]] = None,
) -> Optional[Path]:
    """Create conditions spreadsheet listing each question's code, text, type, and levels.

    routine_labels, when given, is a list parallel to `questions` naming
    which PsychoPy routine each question belongs to -- adds a `routine`
    column. Omitted for the existing single-routine callers, so their CSV
    shape is unchanged.
    """
    conditions_data = []

    for index, q in enumerate(questions):
        row = {}
        if routine_labels is not None:
            row["routine"] = routine_labels[index]
        row["question_code"] = q["code"]
        row["question_text"] = q["description"]
        row["question_type"] = determine_component_type(q)

        if q.get("levels"):
            for level_key, level_text in q["levels"].items():
                row[f"level_{level_key}"] = level_text

        conditions_data.append(row)

    if not conditions_data:
        return None

    df = pd.DataFrame(conditions_data)
    csv_path = output_dir / "conditions.csv"
    df.to_csv(csv_path, index=False)

    return csv_path
```

- [ ] **Step 4: Run to verify the extension tests pass and old CSV tests still pass**

Run: `pytest tests/test_pavlovia_exporter.py -k "conditions_csv" -v`
Expected: PASS (both new tests and the pre-existing `test_create_conditions_csv_populates_question_type`/`test_create_conditions_csv_no_dead_items_expansion`).

- [ ] **Step 5: Write the failing test for `generate_pavlovia_from_customization`**

Add to `tests/test_pavlovia_exporter.py` (add `generate_pavlovia_from_customization` to the top import block):

```python
def test_generate_pavlovia_from_customization_builds_one_routine_per_group(tmp_path):
    groups = [
        {
            "name": "Group One",
            "questions": [
                {
                    "questionCode": "g1q1",
                    "displayOrder": 0,
                    "enabled": True,
                    "mandatory": True,
                    "originalData": {"Description": "Group one question"},
                },
            ],
        },
        {
            "name": "Group Two",
            "questions": [
                {
                    "questionCode": "g2q1",
                    "displayOrder": 0,
                    "enabled": True,
                    "mandatory": True,
                    "originalData": {"Description": "Group two question"},
                },
            ],
        },
    ]

    output_dir = tmp_path / "export"
    psyexp_path = generate_pavlovia_from_customization(groups, output_dir, "combo_survey")

    assert psyexp_path == output_dir / "combo_survey.psyexp"
    assert psyexp_path.exists()

    root = ET.parse(psyexp_path).getroot()
    routines_section = root.find("Routines")
    routine_names = [r.get("name") for r in routines_section.findall("Routine")]
    assert routine_names == ["welcome", "Group_One", "Group_Two", "thanks"]

    conditions_df = pd.read_csv(output_dir / "conditions.csv")
    assert list(conditions_df["routine"]) == ["Group_One", "Group_Two"]
    assert (output_dir / "README.md").exists()


def test_generate_pavlovia_from_customization_deduplicates_routine_names(tmp_path):
    def make_group(code):
        return {
            "name": "Same Name",
            "questions": [
                {
                    "questionCode": code,
                    "displayOrder": 0,
                    "enabled": True,
                    "mandatory": True,
                    "originalData": {"Description": code},
                },
            ],
        }

    groups = [make_group("a"), make_group("b")]
    output_dir = tmp_path / "export"
    psyexp_path = generate_pavlovia_from_customization(groups, output_dir, "dup_survey")

    root = ET.parse(psyexp_path).getroot()
    routine_names = [
        r.get("name") for r in root.find("Routines").findall("Routine")
        if r.get("name") not in ("welcome", "thanks")
    ]
    assert routine_names == ["Same_Name", "Same_Name_2"]


def test_generate_pavlovia_from_customization_raises_when_all_groups_empty(tmp_path):
    groups = [{"name": "Empty Group", "questions": [{"questionCode": "q1", "enabled": False, "originalData": {}}]}]
    with pytest.raises(ValueError):
        generate_pavlovia_from_customization(groups, tmp_path / "export", "empty_survey")
```

Add `import pytest` to the top of the test file if not already present (check first — it currently isn't imported).

- [ ] **Step 6: Run to verify failure**

Run: `pytest tests/test_pavlovia_exporter.py -k "generate_pavlovia_from_customization" -v`
Expected: FAIL — `generate_pavlovia_from_customization` not defined.

- [ ] **Step 7: Implement `_unique_routine_name` and `generate_pavlovia_from_customization`**

In `src/converters/pavlovia.py`, add after `_safe_component_name` (after line 201):

```python
def _unique_routine_name(name: str, used: set) -> str:
    """PsychoPy-safe, unique routine name.

    Reuses _safe_component_name's identifier sanitizing and de-duplicates
    collisions with a numeric suffix -- two customizer groups can share a
    display name (e.g. two multi-run duplicates of the same
    questionnaire).
    """
    base = _safe_component_name(name) or "routine"
    candidate = base
    counter = 2
    while candidate in used:
        candidate = f"{base}_{counter}"
        counter += 1
    used.add(candidate)
    return candidate
```

Add after `export_to_pavlovia` (after line 536):

```python
def generate_pavlovia_from_customization(
    groups: List[Dict[str, Any]],
    output_dir: Path,
    experiment_name: str,
    language: Optional[str] = None,
) -> Path:
    """Build a multi-routine Pavlovia/PsychoPy experiment from Survey
    Customizer groups -- one routine per non-empty group, in group order.

    Mirrors export_to_pavlovia's file-writing tail (conditions.csv,
    .psyexp, README.md) but sources questions from the customizer's
    `groups` model (already filtered/reordered/multi-run by the browser)
    via extract_questions_from_customized_group, instead of reading a raw
    PRISM JSON file.

    Raises:
        ValueError: every group came back empty after filtering (e.g. all
            questions disabled) -- there is nothing to export.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    used_names: set = set()
    routine_groups: List[Tuple[str, List[Dict[str, Any]]]] = []
    for group in groups:
        questions = extract_questions_from_customized_group(group, language=language)
        if not questions:
            continue
        routine_name = _unique_routine_name(group.get("name") or "questions", used_names)
        routine_groups.append((routine_name, questions))

    if not routine_groups:
        raise ValueError("No enabled questions found in the selected groups")

    all_questions = [q for _name, questions in routine_groups for q in questions]
    routine_labels = [name for name, questions in routine_groups for _q in questions]
    create_conditions_csv(all_questions, output_dir, routine_labels=routine_labels)

    psyexp_content = build_psyexp_xml_grouped(experiment_name, routine_groups, {})
    psyexp_path = output_dir / f"{experiment_name}.psyexp"
    psyexp_path.write_text(psyexp_content, encoding="utf-8")

    create_readme(output_dir, experiment_name)

    return psyexp_path
```

- [ ] **Step 8: Run to verify the new tests pass**

Run: `pytest tests/test_pavlovia_exporter.py -k "generate_pavlovia_from_customization" -v`
Expected: PASS

- [ ] **Step 9: Run the full test file**

Run: `pytest tests/test_pavlovia_exporter.py -v`
Expected: all PASS, no regressions.

- [ ] **Step 10: Commit**

```bash
git add src/converters/pavlovia.py tests/test_pavlovia_exporter.py
git commit -m "$(cat <<'EOF'
feat: add generate_pavlovia_from_customization

Builds one PsychoPy routine per Survey Customizer group (combining
several questionnaires into one experiment, matching how LimeSurvey
export already combines groups into one .lss), with a combined
conditions.csv carrying a routine column.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Wire Pavlovia into the Customizer export handler

**Files:**
- Modify: `app/src/web/blueprints/tools_survey_customizer_handlers.py:1-11` (imports), `:206-364` (`handle_survey_customizer_export`, `get_survey_customizer_formats_payload`)
- Test: `tests/test_tools_survey_customizer_handlers.py`

**Interfaces:**
- Consumes: `src.converters.pavlovia.generate_pavlovia_from_customization` (Task 3).
- Produces: `handle_survey_customizer_export` now returns a `.zip` (mimetype `application/zip`) when `data["exportFormat"] == "pavlovia"`, alongside the existing `.lss` behavior for `"limesurvey"`; any other value still 400s.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_tools_survey_customizer_handlers.py`:

```python
def test_handle_survey_customizer_export_pavlovia_returns_zip(monkeypatch) -> None:
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )
    pavlovia = importlib.import_module("src.converters.pavlovia")

    def fake_generate_pavlovia_from_customization(*, groups, output_dir, experiment_name, language):
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{experiment_name}.psyexp").write_text("<xml/>", encoding="utf-8")
        (output_dir / "README.md").write_text("readme", encoding="utf-8")
        return output_dir / f"{experiment_name}.psyexp"

    monkeypatch.setattr(
        pavlovia,
        "generate_pavlovia_from_customization",
        fake_generate_pavlovia_from_customization,
    )

    app = Flask(__name__)
    app.add_url_rule(
        "/api/survey-customizer/export",
        view_func=lambda: handlers.handle_survey_customizer_export(
            data={
                "survey": {"title": "Demo Survey", "language": "en"},
                "groups": [{"id": "g1", "name": "Group 1", "questions": []}],
                "exportFormat": "pavlovia",
            },
            project_path=None,
        ),
        methods=["POST"],
    )

    with app.test_client() as client:
        response = client.post("/api/survey-customizer/export")

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert response.headers["Content-Disposition"].endswith('.zip"')


def test_handle_survey_customizer_export_unknown_format_400() -> None:
    handlers = importlib.import_module(
        "src.web.blueprints.tools_survey_customizer_handlers"
    )

    app = Flask(__name__)
    app.add_url_rule(
        "/api/survey-customizer/export",
        view_func=lambda: handlers.handle_survey_customizer_export(
            data={
                "survey": {"title": "Demo Survey"},
                "groups": [{"id": "g1"}],
                "exportFormat": "qualtrics",
            },
            project_path=None,
        ),
        methods=["POST"],
    )

    with app.test_client() as client:
        response = client.post("/api/survey-customizer/export")

    assert response.status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_tools_survey_customizer_handlers.py -k "pavlovia or unknown_format" -v`
Expected: FAIL — pavlovia format currently 400s unconditionally (`Export format 'pavlovia' not yet supported`), so the zip test fails; the unknown-format test may already incidentally pass (keep it — it pins down behavior across the refactor in Step 3).

- [ ] **Step 3: Add `zipfile` import**

In `app/src/web/blueprints/tools_survey_customizer_handlers.py`, add to the import block at the top (after line 7, `import uuid`):

```python
import zipfile
```

- [ ] **Step 4: Rewrite `handle_survey_customizer_export` to dispatch on format**

Replace the function body (lines 206-323) with:

```python
def handle_survey_customizer_export(data, project_path):
    """Export customized survey groups to LimeSurvey (.lss) or Pavlovia/PsychoPy (.zip)."""
    export_format = data.get("exportFormat", "limesurvey")
    if export_format not in ("limesurvey", "pavlovia"):
        return (
            jsonify({"error": f"Export format '{export_format}' not yet supported"}),
            400,
        )

    if export_format == "limesurvey":
        try:
            from src.limesurvey_exporter import generate_lss_from_customization
        except ImportError:
            return jsonify({"error": "LimeSurvey exporter not available"}), 500
    else:
        try:
            from src.converters.pavlovia import generate_pavlovia_from_customization
        except ImportError:
            return jsonify({"error": "Pavlovia exporter not available"}), 500

    survey_info = data.get("survey", {})
    groups = data.get("groups", [])
    export_options = data.get("exportOptions", {})
    save_to_project = data.get("saveToProject", False)

    if not groups:
        return jsonify({"error": "No groups to export"}), 400

    survey_title = survey_info.get("title", "").strip()
    if not survey_title:
        return jsonify({"error": "Survey name is required"}), 400

    language = survey_info.get("language", "en")
    languages = survey_info.get("languages") or data.get("languages") or [language]
    base_language = (
        survey_info.get("base_language") or data.get("base_language") or language
    )
    ls_version = export_options.get("ls_version", "3")
    matrix_mode = export_options.get("matrix", True)
    matrix_global = export_options.get("matrix_global", True)
    ls_settings = data.get("lsSettings") or {}

    templates_saved = 0
    if save_to_project:
        try:
            project_root = require_existing_project_root(
                project_path,
                missing_message="No active project selected. Open a project before saving templates.",
                missing_path_message="The selected project path no longer exists. Reopen the project and retry the export.",
            )
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 400

        lib_dir = project_root / "code" / "library" / "survey"
        try:
            lib_dir.mkdir(parents=True, exist_ok=True)
            seen = set()
            for group in groups:
                source_path = group.get("sourceFile") or ""
                if not source_path or source_path in seen:
                    continue
                seen.add(source_path)

                src_path = Path(source_path)
                if not src_path.is_file():
                    continue

                dest = lib_dir / src_path.name
                try:
                    dest.resolve().relative_to(lib_dir.resolve())
                    if src_path.resolve() == dest.resolve():
                        continue
                except ValueError:
                    pass

                shutil.copy2(str(src_path), str(dest))
                templates_saved += 1
        except OSError:
            pass

    safe_title = re.sub(r"[^\w\s-]", "", survey_title)
    safe_title = re.sub(r"[\s]+", "_", safe_title).strip("_")
    if not safe_title:
        safe_title = "survey"
    date_str = datetime.now().strftime("%Y-%m-%d")

    if export_format == "limesurvey":
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".lss")
            os.close(fd)

            try:
                generate_lss_from_customization(
                    groups=groups,
                    output_path=temp_path,
                    language=language,
                    languages=languages,
                    base_language=base_language,
                    ls_version=ls_version,
                    matrix_mode=matrix_mode,
                    matrix_global=matrix_global,
                    survey_title=survey_title,
                    ls_settings=ls_settings,
                )
                lss_bytes = Path(temp_path).read_bytes()
            finally:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

            response = send_file(
                io.BytesIO(lss_bytes),
                as_attachment=True,
                download_name=f"{safe_title}_{date_str}.lss",
                mimetype="application/xml",
            )
        except Exception as error:
            return jsonify({"error": str(error)}), 500
    else:
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                output_dir = Path(tmp_dir) / "export"
                generate_pavlovia_from_customization(
                    groups=groups,
                    output_dir=output_dir,
                    experiment_name=safe_title,
                    language=base_language,
                )

                zip_fd, zip_path = tempfile.mkstemp(suffix=".zip")
                os.close(zip_fd)
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for file_path in output_dir.rglob("*"):
                        if file_path.is_file():
                            zf.write(file_path, file_path.relative_to(output_dir))

            response = send_file(
                zip_path,
                as_attachment=True,
                download_name=f"{safe_title}_{date_str}.zip",
                mimetype="application/zip",
            )
            response.call_on_close(lambda: os.unlink(zip_path))
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except Exception as error:
            return jsonify({"error": str(error)}), 500

    if templates_saved:
        response.headers["X-Templates-Saved"] = str(templates_saved)
        response.headers["Access-Control-Expose-Headers"] = "X-Templates-Saved"
    return response
```

- [ ] **Step 5: Update `get_survey_customizer_formats_payload`**

Replace the function (lines 326-364) with:

```python
def get_survey_customizer_formats_payload():
    """List available export formats for the survey customizer."""
    return {
        "formats": [
            {
                "id": "limesurvey",
                "name": "LimeSurvey",
                "extension": ".lss",
                "description": "LimeSurvey Survey Structure file",
                "options": [
                    {
                        "id": "ls_version",
                        "name": "LimeSurvey Version",
                        "type": "select",
                        "default": "6",
                        "choices": [
                            {
                                "value": "6",
                                "label": "LimeSurvey 5.x / 6.x (Modern)",
                            },
                            {"value": "3", "label": "LimeSurvey 3.x (Legacy)"},
                        ],
                    },
                    {
                        "id": "matrix",
                        "name": "Group as matrices",
                        "type": "boolean",
                        "default": True,
                    },
                    {
                        "id": "matrix_global",
                        "name": "Global matrix grouping",
                        "type": "boolean",
                        "default": True,
                    },
                ],
            },
            {
                "id": "pavlovia",
                "name": "Pavlovia/PsychoPy",
                "extension": ".zip",
                "description": "PsychoPy Builder experiment packaged with a conditions spreadsheet and README",
                "options": [],
            },
        ],
    }
```

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `pytest tests/test_tools_survey_customizer_handlers.py -k "pavlovia or unknown_format" -v`
Expected: PASS

- [ ] **Step 7: Run the full test file to confirm no regressions**

Run: `pytest tests/test_tools_survey_customizer_handlers.py -v`
Expected: all PASS, including the pre-existing `test_handle_survey_customizer_export_cleans_up_temp_file` and `test_handle_survey_customizer_export_survives_cleanup_failure`.

- [ ] **Step 8: Commit**

```bash
git add app/src/web/blueprints/tools_survey_customizer_handlers.py tests/test_tools_survey_customizer_handlers.py
git commit -m "$(cat <<'EOF'
feat: dispatch Survey Customizer export to Pavlovia or LimeSurvey

handle_survey_customizer_export now branches on exportFormat instead
of hard-rejecting anything but limesurvey, zipping the multi-routine
Pavlovia experiment the same way the Survey Export screen's own
Pavlovia endpoint already does. get_survey_customizer_formats_payload
lists both formats.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Add the Pavlovia option to the Customize Export UI (template)

**Files:**
- Modify: `app/templates/survey_customizer.html:84,90-113,116,141,175`

**Interfaces:**
- Produces: a `.limesurvey-only` CSS class marking every LimeSurvey-specific settings block, and a `#pavloviaLanguageNote` element — both consumed by Task 6's JS.

- [ ] **Step 1: Update the Survey Name helper text**

At line 84, replace:

```html
<small class="text-muted">This name will appear as the survey title in LimeSurvey</small>
```

with:

```html
<small class="text-muted">This name will appear as the survey/experiment title in the exported file</small>
```

- [ ] **Step 2: Add Pavlovia to the Target Tool select**

At lines 90-94, replace:

```html
<select class="form-select" id="targetTool">
    <option value="limesurvey" selected>LimeSurvey</option>
    <!-- Future: <option value="redcap">REDCap</option> -->
    <!-- Future: <option value="qualtrics">Qualtrics</option> -->
</select>
```

with:

```html
<select class="form-select" id="targetTool">
    <option value="limesurvey" selected>LimeSurvey</option>
    <option value="pavlovia">Pavlovia/PsychoPy</option>
    <!-- Future: <option value="redcap">REDCap</option> -->
    <!-- Future: <option value="qualtrics">Qualtrics</option> -->
</select>
```

- [ ] **Step 3: Add the Pavlovia single-language note**

At line 103, after the existing `<small class="text-muted">Set from Survey Generator</small>`, add:

```html
<small class="text-muted d-none" id="pavloviaLanguageNote">Pavlovia export uses the base language only.</small>
```

- [ ] **Step 4: Add Pavlovia to the Export Format select**

At lines 111-113, replace:

```html
<select class="form-select" id="exportFormat">
    <option value="limesurvey" selected>LimeSurvey (.lss)</option>
</select>
```

with:

```html
<select class="form-select" id="exportFormat">
    <option value="limesurvey" selected>LimeSurvey (.lss)</option>
    <option value="pavlovia">Pavlovia (.zip)</option>
</select>
```

- [ ] **Step 5: Mark the LimeSurvey Version column as LimeSurvey-only**

At line 116, replace:

```html
                <div class="col-md-4">
                    <div class="export-option">
                        <label class="form-label">LimeSurvey Version
```

with:

```html
                <div class="col-md-4 limesurvey-only">
                    <div class="export-option">
                        <label class="form-label">LimeSurvey Version
```

- [ ] **Step 6: Mark the matrix-grouping checkboxes row as LimeSurvey-only**

At line 141, replace:

```html
            <div class="row mt-2">
                <div class="col-md-6">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="matrixMode" checked>
```

with:

```html
            <div class="row mt-2 limesurvey-only">
                <div class="col-md-6">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="matrixMode" checked>
```

- [ ] **Step 7: Mark the LimeSurvey Survey Settings accordion as LimeSurvey-only**

At line 175, replace:

```html
        <div class="ls-settings-section" id="lsSettingsSection">
```

with:

```html
        <div class="ls-settings-section limesurvey-only" id="lsSettingsSection">
```

- [ ] **Step 8: Manually sanity-check the template renders**

Run: `python3 -c "import ast; from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('app/templates')); env.get_template('survey_customizer.html')"`
Expected: no exception (confirms the Jinja template still parses after the edits — no automated render test exists for this template).

- [ ] **Step 9: Commit**

```bash
git add app/templates/survey_customizer.html
git commit -m "$(cat <<'EOF'
feat: add Pavlovia/PsychoPy option to Customize Export template

Adds the missing pavlovia <option> to both Target Tool and Export
Format selects, and marks every LimeSurvey-specific settings block
with a shared .limesurvey-only class so Task 6's JS can hide them
when Pavlovia is selected.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Toggle LimeSurvey-only options and keep the two format selects in sync (JS)

**Files:**
- Modify: `app/static/js/survey-customizer.js:437` (`loadFromSessionStorage`), `:1389` (near `updateLanguageTags`), `:1743` (near the matrix-mode listener wiring)

**Interfaces:**
- Consumes: `.limesurvey-only` class and `#pavloviaLanguageNote` (Task 5).
- Produces: `syncExportFormat(format)` — sets both `#targetTool` and `#exportFormat` to `format` and calls `updateExportFormatVisibility(format)`.

- [ ] **Step 1: Add `updateExportFormatVisibility`**

In `app/static/js/survey-customizer.js`, add immediately after `updateLanguageTags` (after line 1389):

```javascript
    // Show/hide LimeSurvey-only export options based on the selected format
    function updateExportFormatVisibility(format) {
        document.querySelectorAll('.limesurvey-only').forEach((el) => {
            el.hidden = format !== 'limesurvey';
        });
        const pavloviaNote = document.getElementById('pavloviaLanguageNote');
        if (pavloviaNote) pavloviaNote.classList.toggle('d-none', format !== 'pavlovia');
    }
```

- [ ] **Step 2: Wire the two selects together and to the visibility toggle**

Add after the `globalMatrixInput` listener block (after line 1755-ish, immediately following the existing matrix-mode wiring already at line 1743-1755):

```javascript
    // Keep Target Tool / Export Format in sync and show/hide LimeSurvey-only options
    const targetToolSelect = document.getElementById('targetTool');
    const exportFormatSelect = document.getElementById('exportFormat');
    function syncExportFormat(format) {
        if (targetToolSelect) targetToolSelect.value = format;
        if (exportFormatSelect) exportFormatSelect.value = format;
        updateExportFormatVisibility(format);
    }
    if (targetToolSelect) {
        targetToolSelect.addEventListener('change', (e) => syncExportFormat(e.target.value));
    }
    if (exportFormatSelect) {
        exportFormatSelect.addEventListener('change', (e) => syncExportFormat(e.target.value));
    }
    updateExportFormatVisibility(exportFormatSelect ? exportFormatSelect.value : 'limesurvey');
```

- [ ] **Step 3: Sync format on session-restored target tool**

In `loadFromSessionStorage`, at line 437, replace:

```javascript
            const targetToolEl = document.getElementById('targetTool');
            if (targetToolEl && data.target_tool) targetToolEl.value = data.target_tool;
```

with:

```javascript
            if (data.target_tool) syncExportFormat(data.target_tool);
```

(`syncExportFormat` is a hoisted function declaration in this same `DOMContentLoaded` closure, defined in Step 2 below this call site in the file but available at call time since `loadFromSessionStorage()` only actually runs from the bottom-of-file `loadFromSessionStorage();` call, after every function in the closure has been defined.)

- [ ] **Step 4: Manual verification (no JS test harness exists for this file)**

Use the `run` skill to start the app, open Survey Customizer with at least one loaded questionnaire, and confirm in the browser:
- Switching **Target Tool** to "Pavlovia/PsychoPy" hides the LimeSurvey Version/matrix checkboxes row and the "LimeSurvey Survey Settings" accordion, and shows the "Pavlovia export uses the base language only" note.
- Switching **Export Format** to "Pavlovia (.zip)" does the same (both selects stay in sync either way).
- Switching back to LimeSurvey restores the hidden sections.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/survey-customizer.js
git commit -m "$(cat <<'EOF'
feat: toggle LimeSurvey-only export options for Pavlovia in Customizer

Target Tool and Export Format now stay in sync, and switching to
Pavlovia hides the LimeSurvey-specific settings blocks added in the
previous commit while surfacing the single-language note.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: End-to-end manual verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite for touched areas**

Run: `pytest tests/test_pavlovia_exporter.py tests/test_tools_survey_customizer_handlers.py tests/test_survey_customizer_workflow_wiring.py tests/test_cli_survey_export_pavlovia.py -v`
Expected: all PASS (includes the untouched CLI/single-file Pavlovia tests, confirming they're unaffected).

- [ ] **Step 2: Exercise the real flow via the `run` skill**

Start PRISM Studio, go to Survey Export, select **two or more** questionnaires from the library, click "Customize Export" (or equivalent transition to the Survey Customizer), switch **Target Tool** to "Pavlovia/PsychoPy", enter a survey/experiment name, and click Export.

- [ ] **Step 3: Verify the downloaded `.zip`**

Unzip the downloaded file and confirm it contains:
- `<experiment_name>.psyexp` with one `Routine` per selected questionnaire (open it as text/XML and check for `<Routine name="...">` entries beyond `welcome`/`thanks`).
- `conditions.csv` with a `routine` column identifying which questionnaire each row came from.
- `README.md`.

- [ ] **Step 4: Verify disabling a question is respected**

In the Customizer, disable one question in one of the selected groups before exporting again; confirm that question's code does not appear in the re-exported `conditions.csv`/`.psyexp`.

- [ ] **Step 5: Verify LimeSurvey export still works unmodified**

Switch Target Tool back to LimeSurvey and export; confirm a working `.lss` still downloads (regression check on the unmodified branch).

No commit for this task — it's verification only, not a code change.

---

## Self-Review Notes

- **Spec coverage:** every section of `2026-09-09-pavlovia-customizer-export-design.md` maps to a task — `build_psyexp_xml_grouped`/wrapper → Task 1; `extract_questions_from_customized_group` → Task 2; `create_conditions_csv` extension + `generate_pavlovia_from_customization` → Task 3; handler dispatch + `get_survey_customizer_formats_payload` → Task 4; template → Task 5; JS → Task 6; testing section → Tasks 1-4 (automated) + Task 7 (manual, as the spec itself calls for since no JS test harness exists here).
- **Placeholder scan:** no TBD/TODO; every step has real code or a real shell command.
- **Type consistency:** `routine_groups: List[Tuple[str, List[Dict[str, Any]]]]` used identically in Task 1's `build_psyexp_xml_grouped` and Task 3's `generate_pavlovia_from_customization`; `create_conditions_csv`'s `routine_labels` parameter name and shape match between Task 3's definition and its call site; `generate_pavlovia_from_customization`'s keyword arguments (`groups`, `output_dir`, `experiment_name`, `language`) match exactly between Task 3's definition and Task 4's call site and its test's fake signature.
