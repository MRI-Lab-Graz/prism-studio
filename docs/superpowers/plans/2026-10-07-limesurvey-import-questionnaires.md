# LimeSurvey Import: One Template per Questionnaire — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importing a `.lss`/`.lsa` in the Template Editor lists the questionnaires it contains (split by group / question / whole survey), loads one at a time as a clean PRISM template with real items, and logs every step to the terminal. The CLI offers the same.

**Architecture:** All logic lives in `src/converters/limesurvey.py`: a parsed survey is split into questionnaires, each built with the existing `_build_prism_template_from_parsed` (which already flattens array rows), then post-processed (stem → `Study.Instructions`, PRISMMETA restore). A thin Flask route and the CLI both call it; the editor reuses its existing Excel group-picker row.

**Tech Stack:** Python 3 (defusedxml, Flask), vanilla ES modules, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-07-limesurvey-import-questionnaires-design.md`

## Global Constraints

- Logic once in the backend (`src/`); the Flask route and JS only call it (repo CLAUDE.md "One implementation").
- TDD: every task writes a failing test first and watches it fail.
- Terminal lines use the `[PRISM]` prefix; the route also prints the equivalent CLI command.
- Item IDs: row code kept when it matches `^[A-Za-z][A-Za-z0-9_]*$` and is unused; otherwise `<parent code>_<row code>`. No zero-padding, no other normalization.
- `Technical.SoftwarePlatform = "LimeSurvey"`, `Technical.AdministrationMethod = "online"`; `SoftwareVersion`, `Citation`, `Category` stay empty unless PRISMMETA supplies them.
- Split modes are exactly `group` (default), `question`, `survey`.
- The real `.venv/survey_archive_939812.lsa` contains participant responses: never copy it into `tests/`, never commit it. Tests use `tests/data/limesurvey_four_questionnaires.lss` (synthetic, already created).
- `parse_lss_xml` (combined mode) is **not** changed: data conversion depends on it.
- Every commit message ends with the attribution trailer given in the session (`Co-Authored-By: ...`); the `git commit -m` lines below omit it for brevity.
- Run all Python via the repo venv: `.venv/bin/python -m pytest ...`.

## Review Focus

1. Group names with umlauts/spaces (`Händigkeit`, `catch the submitted ID1 (via link)`) → task name `handigkeit`, not `hndigkeit` (test in Task 3).
2. LimeSurvey 6 exports keep answer labels only in `<answer_l10ns>` → Levels must carry the labels, not `""` (Task 1; our own exporter writes this format, so the round trip in Task 4 depends on it).
3. Two questionnaires that sanitize to the same task name, or an existing file in `--output` → CLI must refuse to overwrite, not silently replace an edited template (test in Task 6).
4. Garbage upload (not a zip / not XML / `.lsa` without `.lss`) → 400 with a readable message, editor restores its previous state (tests in Tasks 3 and 5).
5. Loading a second questionnaire while the first has unsaved edits → confirm dialog before discarding (Task 7, JS; covered by the existing `hasUnsavedChanges` guard pattern).

Known limit (not in scope): multi-language surveys keep only the first language's question text, as today (`_parse_lss_structure` "first language wins").

---

### Task 1: LimeSurvey 6 answer labels from `<answer_l10ns>`

**Files:**
- Modify: `src/converters/limesurvey.py` — `_parse_answers_into_questions` (≈ line 331)
- Test: `tests/test_limesurvey_questionnaires.py` (create)

**Interfaces:**
- Consumes: nothing new.
- Produces: `_parse_answers_into_questions(root, questions_map, get_text, *, track_scales=False)` — same signature; now fills labels from `<answer_l10ns>` (keyed by `aid`, one row per language) when the `<answers>` row has no inline `answer`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_limesurvey_questionnaires.py`:

```python
"""LimeSurvey import: one PRISM template per questionnaire (spec 2026-10-07)."""

from __future__ import annotations

from pathlib import Path

import defusedxml.ElementTree as ET

from src.converters.limesurvey import _parse_answers_into_questions

FIXTURE = Path(__file__).parent / "data" / "limesurvey_four_questionnaires.lss"


def _get_text(element, tag):
    child = element.find(tag)
    return (child.text if child is not None else "") or ""


def test_ls6_answer_labels_come_from_answer_l10ns():
    root = ET.fromstring(
        """<document>
          <answers><rows><row><aid>7</aid><qid>1</qid><code>A1</code></row></rows></answers>
          <answer_l10ns><rows>
            <row><aid>7</aid><answer>selten</answer><language>de</language></row>
            <row><aid>7</aid><answer>rarely</answer><language>en</language></row>
          </rows></answer_l10ns>
        </document>"""
    )
    questions_map = {"1": {"levels": {}}}

    _parse_answers_into_questions(root, questions_map, _get_text)

    assert questions_map["1"]["levels"] == {"A1": {"de": "selten", "en": "rarely"}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_questionnaires.py -v`
Expected: FAIL — levels are `{"A1": ""}`.

- [ ] **Step 3: Implement**

In `_parse_answers_into_questions`, after the `rows is None` guard, build the l10n map, then wrap the existing per-row body (everything from `if track_scales:` to the end of the loop) in a loop over `(lang, answer)` pairs:

```python
    # LS 6.x: answer text lives in <answer_l10ns> (one row per language), keyed by aid.
    answer_l10ns = {}
    for l10n in root.findall("answer_l10ns/rows/row"):
        answer_l10ns.setdefault(get_text(l10n, "aid"), []).append(
            (get_text(l10n, "language"), get_text(l10n, "answer"))
        )

    for row in rows.findall("row"):
        qid = get_text(row, "qid")
        code = get_text(row, "code")
        answer = get_text(row, "answer")
        lang = get_text(row, "language")

        if qid not in questions_map:
            continue

        pairs = [(lang, answer)]
        if not answer and get_text(row, "aid") in answer_l10ns:
            pairs = answer_l10ns[get_text(row, "aid")]

        for lang, answer in pairs:
            if track_scales:
                ...  # existing body, indented one level, unchanged
            else:
                ...  # existing body, indented one level, unchanged
```

(The two `...` are the existing `if track_scales:` / `else:` blocks moved one indent level deeper — no other change.)

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_questionnaires.py tests/test_limesurvey_lsq_lsg_import.py tests/test_limesurvey_structure.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/converters/limesurvey.py tests/test_limesurvey_questionnaires.py tests/data/limesurvey_four_questionnaires.lss
git commit -m "fix(limesurvey): read LS 6 answer labels from answer_l10ns"
```

---

### Task 2: Unique, usable item IDs for array rows

**Files:**
- Modify: `src/converters/limesurvey.py` — `_build_prism_template_from_parsed`, subquestion loop (≈ lines 801–817)
- Test: `tests/test_limesurvey_questionnaires.py`

**Interfaces:**
- Produces: `_array_item_id(parent_code: str, row_code: str, taken) -> str`; each array item's `LimeSurvey` block gains `"columnName": "<parent>[<row>]"`.

- [ ] **Step 1: Write the failing test**

Append:

```python
from src.converters.limesurvey import parse_lsg_xml


def test_numeric_row_codes_are_prefixed_with_the_array_code():
    template = parse_lsg_xml(FIXTURE.read_bytes())

    assert "ADS1_1" in template and "ADS1_2" in template
    assert "1" not in template
    assert template["ADS1_1"]["LimeSurvey"]["columnName"] == "ADS1[1]"


def test_identifier_row_codes_are_kept():
    template = parse_lsg_xml(FIXTURE.read_bytes())

    assert "WHO1" in template and "WHO2" in template
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_questionnaires.py -v`
Expected: FAIL — keys are `"1"`, `"2"`.

- [ ] **Step 3: Implement**

Above `_build_prism_template_from_parsed` add:

```python
_ITEM_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _array_item_id(parent_code, row_code, taken):
    """Row code as item ID when it is a usable, unused identifier; otherwise
    prefixed with its array's code (ADS1 + "1" -> "ADS1_1")."""
    if _ITEM_ID_RE.match(row_code) and row_code not in taken:
        return row_code
    return f"{parent_code}_{row_code}"
```

In the subquestion loop replace `prism_questions[sq_code] = entry` with:

```python
                entry["LimeSurvey"]["columnName"] = f"{title}[{sq_code}]"
                prism_questions[_array_item_id(title, sq_code, prism_questions)] = entry
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_questionnaires.py tests/test_limesurvey_lsq_lsg_import.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/converters/limesurvey.py tests/test_limesurvey_questionnaires.py
git commit -m "fix(limesurvey): prefix non-identifier array row codes with the array code"
```

---

### Task 3: Split into questionnaires, build templates, log to terminal

**Files:**
- Modify: `src/converters/limesurvey.py` (add `import io`; new functions after `parse_lsg_xml`)
- Test: `tests/test_limesurvey_questionnaires.py`

**Interfaces:**
- Produces:
  - `SPLIT_MODES = ("group", "question", "survey")`
  - `read_lss_xml(data: bytes, filename: str) -> bytes` — raises `ValueError`
  - `list_limesurvey_questionnaires(xml_content: bytes, split: str = "group", source_name: str = "LimeSurvey file") -> list[dict]` — each `{"key", "name", "item_count", "helper"}`; keys `g<gid>` / `q<qid>` / `survey`; prints the listing
  - `limesurvey_questionnaire_template(xml_content: bytes, key: str, split: str = "group") -> dict` — raises `ValueError` for unknown key; prints a load line
  - `_build_questionnaires(xml_content, split) -> (parsed, [(info, template)])` (used by Task 8)
  - `_apply_prismmeta(template, html) -> list[str]` — stub returning `[]` here, filled in Task 4

- [ ] **Step 1: Write the failing tests**

Append:

```python
import io
import zipfile

import pytest

from src.converters.limesurvey import (
    limesurvey_questionnaire_template,
    list_limesurvey_questionnaires,
    read_lss_xml,
)

XML = FIXTURE.read_bytes()


def test_split_by_group_lists_each_questionnaire(capsys):
    found = list_limesurvey_questionnaires(XML, "group", source_name="survey.lss")

    assert [(q["key"], q["name"], q["item_count"], q["helper"]) for q in found] == [
        ("g10", "catch the submitted ID", 1, True),
        ("g20", "WHO-5", 2, False),
        ("g30", "ADS", 2, False),
        ("g40", "Händigkeit", 1, False),
    ]
    out = capsys.readouterr().out
    assert "[PRISM] LimeSurvey import: survey.lss (DBVersion 636, languages: de)" in out
    assert "[PRISM] Split by group -> 4 questionnaire(s):" in out
    assert "ADS" in out and "(array ADS1)" in out


def test_split_by_question_and_whole_survey():
    by_question = list_limesurvey_questionnaires(XML, "question")
    whole = list_limesurvey_questionnaires(XML, "survey")

    assert [q["name"] for q in by_question] == ["catchsubmittedID", "WHO5", "ADS1", "Hand"]
    assert [(q["key"], q["item_count"]) for q in whole] == [("survey", 6)]


def test_questionnaire_template_has_real_items_and_instructions(capsys):
    template = limesurvey_questionnaire_template(XML, "g30", "group")

    items = [k for k in template if k not in ("Technical", "Study", "Metadata", "I18n")]
    assert items == ["ADS1_1", "ADS1_2"]
    assert template["ADS1_1"]["Description"] == {"de": "war ich bedrückt"}
    assert template["ADS1_1"]["Levels"] == {"0": {"de": "selten"}, "1": {"de": "meistens"}}
    assert template["Study"]["Instructions"] == {"de": "Während der letzten Woche..."}
    assert template["Study"]["OriginalName"] == "ADS"
    assert template["Study"]["TaskName"] == "ads"
    assert template["Technical"]["AdministrationMethod"] == "online"
    assert "[PRISM] Loading g30 'ADS': 2 item(s)" in capsys.readouterr().out


def test_group_description_and_umlaut_task_name():
    who = limesurvey_questionnaire_template(XML, "g20")
    hand = limesurvey_questionnaire_template(XML, "g40")

    assert who["Study"]["Description"] == "Wohlbefinden"
    assert who["Study"]["TaskName"] == "who5"
    assert hand["Study"]["TaskName"] == "handigkeit"
    assert hand["Hand"]["Levels"] == {"L": {"de": "links"}, "R": {"de": "rechts"}}


def test_unknown_key_lists_valid_keys():
    with pytest.raises(ValueError, match="Valid keys: g10, g20, g30, g40"):
        limesurvey_questionnaire_template(XML, "g99")


def test_unknown_split_mode_is_rejected():
    with pytest.raises(ValueError, match="Unknown split mode"):
        list_limesurvey_questionnaires(XML, "pages")


def _zip(**members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_read_lss_xml_unpacks_lsa_and_rejects_garbage():
    assert read_lss_xml(XML, "x.lss") == XML
    assert read_lss_xml(_zip(**{"survey_1.lss": XML, "survey_1_responses.lsr": b""}), "x.lsa") == XML
    with pytest.raises(ValueError, match="not a valid .lsa archive"):
        read_lss_xml(b"not a zip", "x.lsa")
    with pytest.raises(ValueError, match="No .lss file found"):
        read_lss_xml(_zip(**{"readme.txt": b"hi"}), "x.lsa")
    with pytest.raises(ValueError, match="Unsupported file type"):
        read_lss_xml(XML, "x.txt")
    with pytest.raises(ValueError, match="Invalid LimeSurvey XML"):
        list_limesurvey_questionnaires(b"<not xml")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_questionnaires.py -v`
Expected: FAIL — `ImportError: cannot import name 'limesurvey_questionnaire_template'`.

- [ ] **Step 3: Implement**

Add `import io` to the imports. After `parse_lsg_xml` add:

```python
SPLIT_MODES = ("group", "question", "survey")
_ARRAY_TYPES = {"F", "A", "B", "C", "E", "H", "1", ";", ":"}
# Text, equation and display questions: no answer options of their own.
_HELPER_TYPES = {"S", "T", "U", "Q", "*", "X"}
_PRISMMETA_RE = re.compile(r"^PRISMMETA", re.IGNORECASE)
_TEMPLATE_SECTIONS = {"Technical", "Study", "Metadata", "I18n", "LimeSurvey", "Scoring", "Normative"}


def read_lss_xml(data, filename):
    """Return the .lss XML from an uploaded .lss file or .lsa archive."""
    name = filename.lower()
    if name.endswith(".lss"):
        return data
    if not name.endswith(".lsa"):
        raise ValueError("Unsupported file type. Use .lss or .lsa")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            lss_names = [n for n in archive.namelist() if n.endswith(".lss")]
            if not lss_names:
                raise ValueError(f"No .lss file found inside {filename}")
            return archive.read(lss_names[0])
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{filename} is not a valid .lsa archive") from exc


def _task_name(name):
    # Transliterate first: sanitize_task_name drops non-ASCII ("Händigkeit" -> "hndigkeit").
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return sanitize_task_name(ascii_name) or "imported"


def _parse_lss_for_questionnaires(xml_content):
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid LimeSurvey XML: {exc}") from exc

    def get_text(element, tag):
        child = element.find(tag)
        return (child.text if child is not None else "") or ""

    questions_map, groups_map = _parse_lss_structure(root, get_text)
    _parse_answers_into_questions(root, questions_map, get_text)
    languages, default_language = _detect_languages(root, get_text)
    return {
        "questions": questions_map,
        "groups": groups_map,
        "languages": languages,
        "default_language": default_language,
        "title": _parse_survey_metadata(root, get_text).get("title") or "survey",
        "db_version": get_text(root, "DBVersion"),
    }


def _split_questionnaires(parsed, split):
    if split not in SPLIT_MODES:
        raise ValueError(f"Unknown split mode '{split}'. Use one of: {', '.join(SPLIT_MODES)}")
    groups = parsed["groups"]
    top = sorted(
        (
            (qid, q)
            for qid, q in parsed["questions"].items()
            if q.get("parent_qid") in (None, "", "0")
        ),
        key=lambda item: (groups.get(item[1]["gid"], {}).get("order", 0), item[1]["question_order"]),
    )
    prismmeta = {
        q["gid"]: str(q["attributes"].get("equation", ""))
        for _qid, q in top
        if _PRISMMETA_RE.match(q["title"])
    }
    top = [(qid, q) for qid, q in top if not _PRISMMETA_RE.match(q["title"])]

    if split == "survey":
        if not top:
            return []
        return [{"key": "survey", "name": parsed["title"], "description": "",
                 "qids": [qid for qid, _ in top], "prismmeta": ""}]
    if split == "question":
        return [{"key": f"q{qid}", "name": q["title"], "description": "",
                 "qids": [qid], "prismmeta": ""} for qid, q in top]
    parts = []
    for gid, group in sorted(groups.items(), key=lambda g: g[1]["order"]):
        qids = [qid for qid, q in top if q["gid"] == gid]
        if qids:
            parts.append({"key": f"g{gid}", "name": group["name"] or f"group {gid}",
                          "description": group["description"], "qids": qids,
                          "prismmeta": prismmeta.get(gid, "")})
    return parts


def _apply_prismmeta(template, html):
    """Restore what the exporter stored in a group's hidden PRISMMETA question.
    Returns the names of the restored fields."""
    return []


def _questionnaire_template(parsed, part):
    questions = {qid: parsed["questions"][qid] for qid in part["qids"]}
    lang = parsed["default_language"]
    template = _build_prism_template_from_parsed(
        questions, parsed["groups"], parsed["languages"], lang, source_type="lss"
    )
    study = template["Study"]
    study["OriginalName"] = part["name"]
    study["TaskName"] = _task_name(part["name"])
    if part["description"]:
        study["Description"] = part["description"]
    stems = [
        q["question"]
        for q in questions.values()
        if q["type"] in _ARRAY_TYPES and q["subquestions"] and q["question"]
    ]
    if stems:
        study["Instructions"] = {lang: "\n\n".join(stems)}
    template["Technical"]["AdministrationMethod"] = "online"
    return template, _apply_prismmeta(template, part["prismmeta"])


def _build_questionnaires(xml_content, split):
    parsed = _parse_lss_for_questionnaires(xml_content)
    results = []
    for part in _split_questionnaires(parsed, split):
        template, restored = _questionnaire_template(parsed, part)
        questions = [parsed["questions"][qid] for qid in part["qids"]]
        results.append((
            {
                "key": part["key"],
                "name": part["name"],
                "item_count": len([k for k in template if k not in _TEMPLATE_SECTIONS]),
                "helper": all(
                    q["type"] in _HELPER_TYPES and not q["levels"] and not q["subquestions"]
                    for q in questions
                ),
                "arrays": [q["title"] for q in questions if q["type"] in _ARRAY_TYPES and q["subquestions"]],
                "restored": restored,
            },
            template,
        ))
    return parsed, results


def list_limesurvey_questionnaires(xml_content, split="group", source_name="LimeSurvey file"):
    """List the questionnaires in a LimeSurvey survey, split by group, question or whole survey."""
    parsed, results = _build_questionnaires(xml_content, split)
    print(
        f"[PRISM] LimeSurvey import: {source_name} (DBVersion {parsed['db_version'] or '?'}, "
        f"languages: {', '.join(parsed['languages'])})"
    )
    print(f"[PRISM] Split by {split} -> {len(results)} questionnaire(s):")
    for info, _template in results:
        line = f"[PRISM]   {info['key']:<8} {info['name']}  {info['item_count']} item(s)"
        if info["arrays"]:
            line += f"  (array {', '.join(info['arrays'])})"
        if info["helper"]:
            line += "  [helper: no answer options]"
        print(line)
    return [{k: info[k] for k in ("key", "name", "item_count", "helper")} for info, _ in results]


def limesurvey_questionnaire_template(xml_content, key, split="group"):
    """Build the PRISM template for one questionnaire (key from list_limesurvey_questionnaires)."""
    _parsed, results = _build_questionnaires(xml_content, split)
    for info, template in results:
        if info["key"] == key:
            stem = "stem -> Study.Instructions" if "Instructions" in template["Study"] else "no array stem"
            meta = (
                f"PRISMMETA restored: {', '.join(info['restored'])}"
                if info["restored"]
                else "no PRISMMETA (fill in Citation, Category, SoftwareVersion by hand)"
            )
            print(f"[PRISM] Loading {key} '{info['name']}': {info['item_count']} item(s), {stem}, {meta}")
            return template
    valid = ", ".join(info["key"] for info, _ in results) or "none"
    raise ValueError(f"No questionnaire '{key}' (split by {split}). Valid keys: {valid}")
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_questionnaires.py -v`
Expected: all PASS. If the WHO stem assertion or helper flag differs, read `_parse_lss_structure` output for the fixture before changing code.

- [ ] **Step 5: Commit**

```bash
git add src/converters/limesurvey.py tests/test_limesurvey_questionnaires.py
git commit -m "feat(limesurvey): split a survey into questionnaire templates with terminal log"
```

---

### Task 4: PRISMMETA round trip (PRISM → LimeSurvey → PRISM)

**Files:**
- Modify: `src/converters/limesurvey.py` — `_apply_prismmeta`
- Test: `tests/test_limesurvey_questionnaires.py`

**Interfaces:**
- Consumes: `_extract_prismmeta(prism_json) -> dict[str, str]` and `parse_prismmeta_codemap(fields) -> dict[sanitized, original]` from `src.converters.survey_templates` (physical file `app/src/converters/survey_templates.py`); `generate_lss(json_files, output_path=None, language="en", ...)` from `src.limesurvey_exporter`.
- Produces: `_apply_prismmeta(template, html) -> list[str]` filled in.

- [ ] **Step 1: Write the failing test**

Append:

```python
import json


def test_prism_template_survives_limesurvey_round_trip(tmp_path):
    from src.limesurvey_exporter import generate_lss

    original = {
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv",
                      "SoftwarePlatform": "LimeSurvey", "Language": "de",
                      "Respondent": "self", "AdministrationMethod": "online"},
        "Study": {"TaskName": "rts", "OriginalName": "Round Trip Scale", "ShortName": "RTS",
                  "Citation": "Doe 2020", "Authors": ["Doe J"], "LicenseID": "CC-BY-4.0",
                  "Category": "other", "Description": "A test scale",
                  "Instructions": "Bitte antworten Sie."},
        "RTS01": {"Description": "erstes Item", "Levels": {"1": "nie", "2": "oft"}},
        "RTS02": {"Description": "zweites Item", "Levels": {"1": "nie", "2": "oft"}},
    }
    source = tmp_path / "survey-rts.json"
    source.write_text(json.dumps(original), encoding="utf-8")
    lss = tmp_path / "rts.lss"
    generate_lss([str(source)], output_path=str(lss), language="de")
    xml = lss.read_bytes()

    [found] = list_limesurvey_questionnaires(xml)
    template = limesurvey_questionnaire_template(xml, found["key"])

    assert [k for k in template if k.startswith("RTS")] == ["RTS01", "RTS02"]
    assert not [k for k in template if k.upper().startswith("PRISMMETA")]
    assert template["RTS01"]["Levels"] == {"1": {"de": "nie"}, "2": {"de": "oft"}}
    study = template["Study"]
    assert study["OriginalName"] == "Round Trip Scale"
    assert study["ShortName"] == "RTS"
    assert study["Citation"] == "Doe 2020"
    assert study["Authors"] == ["Doe J"]
    assert study["Description"] == "A test scale"
    assert study["Instructions"] == {"de": "Bitte antworten Sie."}
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_questionnaires.py::test_prism_template_survives_limesurvey_round_trip -v`
Expected: FAIL on `ShortName` / `Citation` (stub restores nothing).

- [ ] **Step 3: Implement**

Replace the `_apply_prismmeta` stub:

```python
def _apply_prismmeta(template, html):
    """Restore what the exporter stored in a group's hidden PRISMMETA question.
    Returns the names of the restored fields."""
    if not html:
        return []
    from src.converters.survey_templates import _extract_prismmeta, parse_prismmeta_codemap

    fields = _extract_prismmeta({"PRISMMETA": {"Attributes": {"equation": html}}})
    study = template["Study"]
    restored = []
    for field, target in (("name", "OriginalName"), ("abbrev", "ShortName"),
                          ("doi", "DOI"), ("citation", "Citation"), ("license", "License")):
        if fields.get(field):
            study[target] = fields[field]
            restored.append(target)
    if fields.get("authors"):
        # ponytail: the exporter joins authors with ", ", which also appears inside
        # "Doe, J." names; kept as one entry rather than guessing the split.
        study["Authors"] = [fields["authors"]]
        restored.append("Authors")
    codemap = parse_prismmeta_codemap(fields)
    if any(code in template for code in codemap):
        renamed = {codemap.get(k, k): v for k, v in template.items()}
        template.clear()
        template.update(renamed)
        restored.append("CodeMap")
    return restored
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_questionnaires.py -v`
Expected: all PASS. If the exporter writes items or levels in a shape the importer doesn't yet read, inspect `rt.lss` (`grep -o "<title>[^<]*</title>"`) and fix the importer side — never the assertion.

- [ ] **Step 5: Commit**

```bash
git add src/converters/limesurvey.py tests/test_limesurvey_questionnaires.py
git commit -m "feat(limesurvey): restore PRISMMETA metadata on import (round trip)"
```

---

### Task 5: API route `/api/template-editor/import-limesurvey`

**Files:**
- Modify: `app/src/web/blueprints/tools_template_editor_blueprint.py` (new route after `api_template_editor_import_lsq_lsg`, ≈ line 581)
- Test: `tests/test_template_editor_import_limesurvey_route.py` (create)

**Interfaces:**
- Consumes: Task 3 functions.
- Produces: `POST /api/template-editor/import-limesurvey`, form fields `file`, `split` (default `group`), optional `key`.
  - no key → `200 {"questionnaires": [...], "split": "group"}`
  - key → `200 {"template", "suggested_filename", "item_count", "languages"}`
  - bad input → `400 {"error": "..."}`

- [ ] **Step 1: Write the failing test**

```python
"""POST /api/template-editor/import-limesurvey: list, then load one questionnaire."""

from __future__ import annotations

import io
import os
from pathlib import Path

from flask import Flask

FIXTURE = Path(__file__).parent / "data" / "limesurvey_four_questionnaires.lss"


def _client():
    import importlib

    module = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(module.tools_template_editor_bp)
    return app.test_client()


def _post(client, data=None, name="survey.lss", content=None):
    form = {"file": (io.BytesIO(content or FIXTURE.read_bytes()), name), **(data or {})}
    return client.post("/api/template-editor/import-limesurvey", data=form,
                       content_type="multipart/form-data")


def test_lists_questionnaires_and_prints_cli_equivalent(capsys):
    response = _post(_client())

    assert response.status_code == 200
    body = response.get_json()
    assert [q["key"] for q in body["questionnaires"]] == ["g10", "g20", "g30", "g40"]
    assert body["split"] == "group"
    out = capsys.readouterr().out
    assert "prism_tools.py survey import-limesurvey --input survey.lss --split group" in out


def test_loads_one_questionnaire():
    response = _post(_client(), {"split": "group", "key": "g30"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["item_count"] == 2
    assert body["suggested_filename"] == "survey-ads.json"
    assert body["languages"] == ["de"]
    assert "ADS1_1" in body["template"]


def test_bad_input_is_a_400_with_message():
    client = _client()

    assert _post(client, {"key": "g99"}).get_json()["error"].startswith("No questionnaire 'g99'")
    assert _post(client, {"key": "g99"}).status_code == 400
    assert _post(client, name="x.lsa", content=b"junk").status_code == 400
    assert client.post("/api/template-editor/import-limesurvey", data={}).status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_template_editor_import_limesurvey_route.py -v`
Expected: FAIL with 404.

- [ ] **Step 3: Implement**

```python
@tools_template_editor_bp.route("/api/template-editor/import-limesurvey", methods=["POST"])
def api_template_editor_import_limesurvey():
    """List the questionnaires in a .lss/.lsa (no 'key') or return one as a
    PRISM template ('key'). Same backend as `survey import-limesurvey`."""
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"error": "No file uploaded"}), 400
    split = (request.form.get("split") or "group").strip()
    key = (request.form.get("key") or "").strip()

    from src.converters.limesurvey import (
        limesurvey_questionnaire_template,
        list_limesurvey_questionnaires,
        read_lss_xml,
    )

    command = f"python prism_tools.py survey import-limesurvey --input {file.filename} --split {split}"
    print(f"[PRISM] CLI equivalent: {command}" + (f" --select {key} --output <dir>" if key else ""))
    try:
        xml = read_lss_xml(file.read(), file.filename)
        if not key:
            questionnaires = list_limesurvey_questionnaires(xml, split, source_name=file.filename)
            return jsonify({"questionnaires": questionnaires, "split": split}), 200
        template = _strip_template_editor_internal_keys(
            limesurvey_questionnaire_template(xml, key, split)
        )
    except ValueError as e:
        print(f"[PRISM] LimeSurvey import failed: {e}")
        return jsonify({"error": str(e)}), 400

    i18n = template.get("I18n") or {}
    languages = i18n.get("Languages") or [template.get("Technical", {}).get("Language", "en")]
    reserved = {"Technical", "Study", "Metadata", "I18n", "LimeSurvey", "Scoring", "Normative"}
    return jsonify({
        "template": template,
        "suggested_filename": f"survey-{template['Study']['TaskName']}.json",
        "item_count": len([k for k in template if k not in reserved]),
        "languages": languages,
    }), 200
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_template_editor_import_limesurvey_route.py tests/test_template_editor_import_lsq_lsg_route.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/web/blueprints/tools_template_editor_blueprint.py tests/test_template_editor_import_limesurvey_route.py
git commit -m "feat(template-editor): import-limesurvey route (list, then load one questionnaire)"
```

---

### Task 6: CLI `survey import-limesurvey --split/--list/--select/--output`

**Files:**
- Modify: `app/src/cli/parser.py` (≈ lines 1782–1792), `app/src/cli/commands/survey.py` — `cmd_survey_import_limesurvey` (≈ line 569)
- Test: `tests/test_cli_survey_commands_remaining.py` — replace `TestCmdSurveyImportLimesurvey`

**Interfaces:**
- Consumes: Task 3 functions.
- Produces: `prism_tools.py survey import-limesurvey --input FILE [--split group|question|survey] [--list] [--select KEY ...|all] [--output DIR]`. Without `--select` it only lists. Writes `DIR/survey-<TaskName>.json`; refuses to overwrite.

- [ ] **Step 1: Write the failing tests**

Replace the `TestCmdSurveyImportLimesurvey` class with:

```python
FOUR_QUESTIONNAIRES = Path(__file__).parent / "data" / "limesurvey_four_questionnaires.lss"


def _limesurvey_args(**overrides):
    values = dict(input=str(FOUR_QUESTIONNAIRES), split="group", list=False, select=None, output=None)
    values.update(overrides)
    return SimpleNamespace(**values)


class TestCmdSurveyImportLimesurvey:
    def test_without_select_only_lists(self, tmp_path, capsys):
        cmd_survey_import_limesurvey(_limesurvey_args(output=str(tmp_path)))

        assert "Split by group -> 4 questionnaire(s)" in capsys.readouterr().out
        assert list(tmp_path.iterdir()) == []

    def test_select_all_writes_one_json_per_questionnaire(self, tmp_path):
        cmd_survey_import_limesurvey(_limesurvey_args(select=["all"], output=str(tmp_path)))

        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "survey-ads.json", "survey-catchthesubmittedid.json",
            "survey-handigkeit.json", "survey-who5.json",
        ]

    def test_refuses_to_overwrite_an_existing_template(self, tmp_path, capsys):
        (tmp_path / "survey-ads.json").write_text("{}", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_import_limesurvey(_limesurvey_args(select=["g30"], output=str(tmp_path)))

        assert exc_info.value.code == 1
        assert "already exists" in capsys.readouterr().out
        assert (tmp_path / "survey-ads.json").read_text(encoding="utf-8") == "{}"

    def test_select_without_output_fails(self, capsys):
        with pytest.raises(SystemExit):
            cmd_survey_import_limesurvey(_limesurvey_args(select=["g30"]))
        assert "--output DIR is required" in capsys.readouterr().out
```

(Ensure `Path` and `pytest` are imported at the top of that file; add if missing.)

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_cli_survey_commands_remaining.py -k ImportLimesurvey -v`
Expected: FAIL (old command calls `convert_lsa_to_prism`).

- [ ] **Step 3: Implement**

`app/src/cli/parser.py` — replace the `--output` / `--task` arguments of `import-limesurvey`:

```python
    parser_survey_limesurvey = survey_subparsers.add_parser(
        "import-limesurvey",
        help="Import the questionnaires of a LimeSurvey .lss/.lsa as PRISM templates. "
        "Matches the Studio Template Editor's 'Import Template Source' for .lss/.lsa.",
    )
    parser_survey_limesurvey.add_argument("--input", required=True, help="Path to .lsa/.lss file")
    parser_survey_limesurvey.add_argument(
        "--split", choices=["group", "question", "survey"], default="group",
        help="One template per question group (default), per question, or for the whole survey",
    )
    parser_survey_limesurvey.add_argument(
        "--list", action="store_true", help="Only list the questionnaires found (default without --select)"
    )
    parser_survey_limesurvey.add_argument(
        "--select", nargs="+", metavar="KEY",
        help="Questionnaire key(s) from the listing (e.g. g30), or 'all'",
    )
    parser_survey_limesurvey.add_argument("--output", help="Directory for the template JSON files")
```

`app/src/cli/commands/survey.py`:

```python
def cmd_survey_import_limesurvey(args):
    """Import LimeSurvey questionnaires as PRISM templates. Matches the Template
    Editor's 'Import Template Source' for .lss/.lsa."""
    from src.converters.limesurvey import (
        limesurvey_questionnaire_template,
        list_limesurvey_questionnaires,
        read_lss_xml,
    )

    input_path = Path(args.input).resolve()
    try:
        xml = read_lss_xml(input_path.read_bytes(), input_path.name)
        found = list_limesurvey_questionnaires(xml, args.split, source_name=input_path.name)
        if args.list or not args.select:
            return
        if not args.output:
            raise ValueError("--output DIR is required with --select")
        keys = [q["key"] for q in found] if args.select == ["all"] else args.select
        out_dir = Path(args.output).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        for key in keys:
            template = limesurvey_questionnaire_template(xml, key, args.split)
            target = out_dir / f"survey-{template['Study']['TaskName']}.json"
            if target.exists():
                raise ValueError(f"{target} already exists; choose another --output directory")
            target.write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"[PRISM] Wrote {target}")
    except (OSError, ValueError) as e:
        print(f"Error importing LimeSurvey: {e}")
        sys.exit(1)
```

Then remove the now-unused `convert_lsa_to_prism` / `check_uniqueness` imports from `survey.py` **only if** nothing else in the file uses them (`grep -n "convert_lsa_to_prism\|check_uniqueness" app/src/cli/commands/survey.py`).

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cli_survey_commands_remaining.py tests/test_prism_tools_cli_contract.py tests/test_cli_dispatch_routing.py -v`
Then: `.venv/bin/python prism_tools.py survey import-limesurvey --input tests/data/limesurvey_four_questionnaires.lss`
Expected: tests PASS; the command prints the 4-line listing.

- [ ] **Step 5: Commit**

```bash
git add app/src/cli/parser.py app/src/cli/commands/survey.py tests/test_cli_survey_commands_remaining.py
git commit -m "feat(cli): survey import-limesurvey lists and writes one template per questionnaire"
```

---

### Task 7: Template Editor — questionnaire picker with "Split by"

**Files:**
- Modify: `app/templates/template_editor.html` (picker row, ≈ lines 87–96)
- Modify: `app/static/js/template-editor.js` (element lookups ≈ line 16–18, context ≈ line 4706–4708)
- Modify: `app/static/js/template-editor/source-workflow.js` (`hideExcelGroupPicker`, `importTemplateSource`, new LimeSurvey functions)
- Test: `tests/test_template_editor_workflow_wiring.py` (lines ≈ 95 and ≈ 409), `tests/e2e/test_template_editor_flows.py`

**Interfaces:**
- Consumes: Task 5 route.
- Produces: context field `sourceSplitSelectEl`; `importLimeSurvey(context, file, previousEditorState)`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_template_editor_workflow_wiring.py` change the pinned endpoint assertion:

```python
        self.assertIn(
            "await context.fetchWithApiFallback('/api/template-editor/import-limesurvey', {",
            workflow_content,
        )
```

and in `test_json_import_is_read_in_the_browser_not_sent_to_a_converter`:

```python
        self.assertLess(json_branch, importer.index("importLimeSurvey("))
```

Append to `tests/e2e/test_template_editor_flows.py`:

```python
from pathlib import Path

FOUR_QUESTIONNAIRES = Path(__file__).parents[1] / "data" / "limesurvey_four_questionnaires.lss"


def test_limesurvey_file_with_several_questionnaires_loads_the_chosen_one(page):
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))

    expect(page.locator("#excelGroupPickerRow")).to_be_visible()
    expect(page.locator("#excelGroupPickerSelect option")).to_have_count(4)
    expect(page.locator("#excelGroupPickerSelect")).to_have_value("g20")  # helper g10 not preselected
    page.select_option("#excelGroupPickerSelect", "g30")
    page.click("#btnLoadExcelGroup")

    expect(page.locator("#alertArea")).to_contain_text("2 item(s) extracted")
    expect(page.get_by_text("ADS1_1").first).to_be_visible()

    page.select_option("#sourceSplitSelect", "survey")
    expect(page.locator("#excelGroupPickerSelect option")).to_have_count(1)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_template_editor_workflow_wiring.py tests/e2e/test_template_editor_flows.py -v`
Expected: wiring tests FAIL (old endpoint); e2e FAIL (picker never shows) or SKIP if Chromium missing — if skipped, say so in the task report.

- [ ] **Step 3: Implement**

`template_editor.html` — replace the picker row contents:

```html
            <div class="mt-2 d-none" id="excelGroupPickerRow">
              <label class="form-label small mb-1" for="excelGroupPickerSelect">Several questionnaires found &mdash; choose one to load:</label>
              <div class="input-group input-group-sm">
                <select class="form-select form-select-sm d-none" id="sourceSplitSelect" title="Split the LimeSurvey file by" style="max-width: 11rem;">
                  <option value="group" selected>Split by group</option>
                  <option value="question">Split by question</option>
                  <option value="survey">Whole survey</option>
                </select>
                <select class="form-select form-select-sm" id="excelGroupPickerSelect"></select>
                <button class="btn btn-outline-primary btn-sm" type="button" id="btnLoadExcelGroup">
                  <i class="fas fa-arrow-right me-1"></i>Load selected
                </button>
              </div>
              <div class="form-text">Load one, check and save it, then load the next from this list.</div>
            </div>
```

`template-editor.js` — next to the other picker lookups add
`const sourceSplitSelectEl = document.getElementById('sourceSplitSelect');`
and pass `sourceSplitSelectEl,` in the context object next to `btnLoadExcelGroup,`.

`source-workflow.js`:

1. `hideExcelGroupPicker` — also hide the split select:

```js
  if (context.sourceSplitSelectEl) {
    context.sourceSplitSelectEl.classList.add('d-none');
  }
```

2. New functions above `importTemplateSource`:

```js
async function fetchLimeSurvey(context, file, fields) {
  const formData = new FormData();
  formData.append('file', file);
  Object.entries(fields).forEach(([name, value]) => formData.append(name, value));
  const res = await context.fetchWithApiFallback('/api/template-editor/import-limesurvey', {
    method: 'POST',
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `Import failed (${res.status})`);
  }
  return data;
}

async function loadLimeSurveyQuestionnaire(context, file, key, previousEditorState) {
  try {
    const data = await fetchLimeSurvey(context, file, { split: context.sourceSplitSelectEl.value, key });
    await finishImport(context, applyImportedTemplate(context, data, file));
  } catch (error) {
    context.restoreEditorState(previousEditorState);
    context.showAlert('danger', `Template import failed: ${context.escapeHtml(error.message)}`);
  }
}

// The backend splits the survey and logs it to the terminal; this only shows the list.
async function importLimeSurvey(context, file, previousEditorState) {
  const { questionnaires } = await fetchLimeSurvey(context, file, { split: context.sourceSplitSelectEl.value });
  if (questionnaires.length === 0) {
    throw new Error('No questionnaires found in the file.');
  }

  context.excelGroupPickerSelectEl.innerHTML = questionnaires
    .map((q) => `<option value="${context.escapeHtml(q.key)}">${context.escapeHtml(q.name)} (${q.item_count} item${q.item_count === 1 ? '' : 's'})${q.helper ? ' (helper)' : ''}</option>`)
    .join('');
  const firstQuestionnaire = questionnaires.find((q) => !q.helper) || questionnaires[0];
  context.excelGroupPickerSelectEl.value = firstQuestionnaire.key;
  context.sourceSplitSelectEl.classList.remove('d-none');
  context.excelGroupPickerRowEl.classList.remove('d-none');

  context.sourceSplitSelectEl.onchange = () => {
    importLimeSurvey(context, file, context.captureEditorState())
      .catch((error) => context.showAlert('danger', context.escapeHtml(error.message)));
  };
  context.btnLoadExcelGroup.onclick = () => {
    if (context.hasUnsavedChanges() && !confirm('You have unsaved changes. Loading another questionnaire will discard them. Continue?')) {
      return;
    }
    loadLimeSurveyQuestionnaire(context, file, context.excelGroupPickerSelectEl.value, context.captureEditorState());
  };

  if (questionnaires.length === 1) {
    await loadLimeSurveyQuestionnaire(context, file, firstQuestionnaire.key, previousEditorState);
    return;
  }
  context.showAlert('info', `Found ${questionnaires.length} questionnaires in ${context.escapeHtml(file.name)}. Choose one above to load it.`);
}
```

3. In `importTemplateSource`, add after the `isExcelCodebook` block:

```js
    if (lowerName.endsWith('.lss') || lowerName.endsWith('.lsa')) {
      await importLimeSurvey(context, file, previousEditorState);
      return;
    }
```

and reduce the remaining `if (isLsqOrLsg) { ... } else { ... }` to just the `.lsq/.lsg` body (delete the `else` branch that posted to `/api/survey-generate-templates` with `mode=combined`).

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_template_editor_workflow_wiring.py tests/e2e/test_template_editor_flows.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/templates/template_editor.html app/static/js/template-editor.js app/static/js/template-editor/source-workflow.js tests/test_template_editor_workflow_wiring.py tests/e2e/test_template_editor_flows.py
git commit -m "feat(template-editor): pick a LimeSurvey questionnaire, split by group/question/survey"
```

---

### Task 8: Survey Generator's group split uses the same builder

**Files:**
- Modify: `src/converters/limesurvey.py` — `parse_lss_xml_by_groups` (≈ line 1278)
- Test: `tests/test_limesurvey_structure.py` (`TestParseLssXmlByGroups`)

**Interfaces:**
- Consumes: `_build_questionnaires(xml_content, "group")` from Task 3.
- Produces: `parse_lss_xml_by_groups(xml_content) -> dict[task_name, template] | None` — same return shape, flattened items.

`parse_lss_xml_by_questions` is left as is (its per-question entries carry extra fields the generator uses); out of scope, note it in the final report.

- [ ] **Step 1: Write the failing test**

Append to `TestParseLssXmlByGroups`:

```python
    def test_array_rows_are_items_not_nested(self):
        from pathlib import Path

        xml = (Path(__file__).parent / "data" / "limesurvey_four_questionnaires.lss").read_bytes()
        result = parse_lss_xml_by_groups(xml)

        assert "ADS1_1" in result["ads"]
        assert "Items" not in result["ads"].get("ADS1", {})
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_structure.py -k ByGroups -v`
Expected: FAIL — `ADS1_1` missing (nested `Items`).

- [ ] **Step 3: Implement**

Replace the body of `parse_lss_xml_by_groups` (keep the name and docstring's first line):

```python
def parse_lss_xml_by_groups(xml_content):
    """Parse a LimeSurvey .lss XML blob and split into separate questionnaires by group.

    Same builder as the Template Editor import: one flattened PRISM template
    per question group, keyed by its task name.
    """
    try:
        _parsed, results = _build_questionnaires(xml_content, "group")
    except ValueError as e:
        print(f"Error parsing XML: {e}")
        return None
    return {template["Study"]["TaskName"]: template for _info, template in results}
```

Delete the now-unreachable old body.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_structure.py tests/test_tools_limesurvey_handlers.py tests/test_lsa_import_integration.py tests/test_limesurvey_e2e.py tests/e2e/test_survey_generator_flows.py -v`
Expected: all PASS. If a Survey Generator test depended on the old nested shape, stop and report it rather than reshaping the new output.

- [ ] **Step 5: Commit**

```bash
git add src/converters/limesurvey.py tests/test_limesurvey_structure.py
git commit -m "fix(survey-generator): group split returns flattened items via the shared builder"
```

---

### Task 9: Verify on the real archive and run the suite

**Files:** none changed.

- [ ] **Step 1:** `.venv/bin/python prism_tools.py survey import-limesurvey --input .venv/survey_archive_939812.lsa`
Expected: 6 questionnaires — catch the submitted ID1 (helper), Laufaktivität (2), WHO-5 (5), Stress (10), ADS (20), Händigkeit (1).

- [ ] **Step 2:** Write to the scratchpad only (never into the repo):
`.venv/bin/python prism_tools.py survey import-limesurvey --input .venv/survey_archive_939812.lsa --select g3132 --output "$TMPDIR/ls-check"` and check that `ADS1_1`..`ADS1_20` have German labels in `Levels`.

- [ ] **Step 3:** `.venv/bin/python -m pytest -q` and `.venv/bin/python tests/verify_repo.py --check dual-tree-drift --no-fix`
Expected: green. Report any failure verbatim.

- [ ] **Step 4:** `git status` — confirm no `.lsa`, no files from the real survey are staged.
