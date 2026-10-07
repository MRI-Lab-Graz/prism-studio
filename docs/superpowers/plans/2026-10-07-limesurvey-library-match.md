# LimeSurvey Import: Match Against the Template Library — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a LimeSurvey questionnaire is chosen in the Template Editor (or listed on the CLI), compare it by question wording with every template in the global and project libraries, show the best match with an exact item-ID mapping, and let the user take the prepared template (aliases keep the survey's codes) only when every imported item maps 1:1.

**Architecture:** One new backend module (`src/converters/library_wording_match.py`) pairs items by wording and grades the match; `src/converters/limesurvey.py` calls it (opt-in) and logs to the terminal; the existing import route and CLI command pass `project_path` / `use_library`; the editor renders a card from what the route returns. The global library is only ever read.

**Tech Stack:** Python 3 (`difflib`, Flask), vanilla ES modules, pytest, vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-07-limesurvey-library-match-design.md` (also read `2026-10-07-limesurvey-import-questionnaires-design.md` for the import it extends)

## Global Constraints

- **The global template folder is never written** by any code in this plan (read-only matching; adopted global templates are saved as project copies by the editor's existing flow). Tests assert the global folder is byte-identical after matching and adopting.
- Logic once in the backend (`src/`); the route and JS only call it/display it (repo CLAUDE.md). Every GUI action has the CLI equivalent (`--project`, `--list`, `--select KEY --use-library`).
- TDD: every task writes a failing test first and watches it fail.
- Standard library only (`difflib`, `re`, `html`, `unicodedata`): no new dependency.
- Thresholds, verbatim: pair `>= 0.85`; `exact` needs every similarity `>= 0.97`; level labels `>= 0.9`; `medium` needs `paired >= 0.7 * n`; templates whose item count differs by more than a factor of two from `n` are skipped.
- Confidence values are exactly `exact`, `high`, `medium`; a match is **adoptable** only for `exact`/`high` without `ids_conflict`.
- Matching is opt-in (`match_library=True`) so existing callers/tests are unaffected; a matching failure never blocks a plain import (`[PRISM] Library match skipped: <reason>`).
- Terminal lines use the `[PRISM]` prefix. The local file path of a library template is never sent to the browser.
- Do not use `_localize_survey_template` for wording (its language-key test misreads Levels keys such as `no`/`ja`); pick languages per value with `survey_templates._pick_language_value`.
- Item IDs are free strings: never zero-pad or normalise them; the loose `_ls_normalize_code` is not used by this module. Session labels are not involved.
- Tests use synthetic libraries in `tmp_path`; never read, copy or commit the real `.venv/survey_archive_939812.lsa`.
- Every commit message ends with the session's attribution trailer (`Co-Authored-By: ...`); the `git commit -m` lines below omit it for brevity.
- Run Python via `.venv/bin/python`; JS tests via `npx vitest run`.

## Review Focus

1. Global library untouched: byte-identical files after `best_library_match` + `apply_library_template` (Task 2) and after the CLI `--use-library` run (Task 5).
2. An imported code equal to a library item's key but paired to a different one (crossed IDs) must not be adoptable (Task 1).
3. Identical wording twice (two "ich war müde") must stay 1:1 by position (Task 1).
4. German import vs bilingual library template matches; vs an English-only one it must not (Task 1).
5. Missing/unreadable library folders, a library item without `Description` (alias-only), an empty project path: no crash, no match (Task 1).
6. A matching exception must not block a plain import and must say so in the terminal (Task 3).

---

### Task 1: Wording matcher (`best_library_match`)

**Files:**
- Create: `src/converters/library_wording_match.py`
- Create: `tests/test_library_wording_match.py`

**Interfaces:**
- Consumes: `src.converters.survey_templates` (`_load_global_templates() -> {key: {"path", "json", "structure"}}`, `_load_project_templates(project_path)`, `_NON_ITEM_TOPLEVEL_KEYS`, `_METADATA_CODE_RE`, `_default_language_from_template(template) -> str`, `_pick_language_value(dict, lang)`).
- Produces: `normalize_wording(text) -> str`, `similarity(a, b) -> float`, `best_library_match(template: dict, project_path=None) -> dict | None` with keys `template_key, source, template_path, template_file, confidence, paired, imported_items, library_items, ids_identical, ids_conflict, adoptable, levels_ok, mean_similarity, id_map, reworded, unpaired_imported, unpaired_library`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_library_wording_match.py`:

```python
"""Library matching by wording (spec 2026-10-07-limesurvey-library-match)."""

from __future__ import annotations

import json

import pytest

from src.converters import library_wording_match as lwm
from src.converters import survey_templates as st

TEXTS = ["war ich bedrückt", "war ich müde", "konnte ich nicht schlafen", "fühlte ich mich einsam"]
LEVELS = {"0": "selten", "1": "manchmal", "2": "meistens"}


def imported(texts=TEXTS, codes=None, levels=LEVELS, lang="de"):
    """A questionnaire as the LimeSurvey import builds it (multilingual dicts)."""
    codes = codes or [f"ADS1_{i}" for i in range(1, len(texts) + 1)]
    template = {"Technical": {"Language": lang}, "Study": {"TaskName": "ads", "OriginalName": "ADS"}}
    for code, text in zip(codes, texts):
        item = {"Description": {lang: text}}
        if levels:
            item["Levels"] = {k: {lang: v} for k, v in levels.items()}
        template[code] = item
    return template


def library_file(directory, name="ads", texts=TEXTS, codes=None, levels=LEVELS, bilingual=False):
    """A library template file (plain strings, like the global library)."""
    codes = codes or [f"ads_{i:02d}" for i in range(1, len(texts) + 1)]
    template = {"Technical": {"Language": "de"}, "Study": {"TaskName": name}}
    for code, text in zip(codes, texts):
        item = {"Description": {"de": text, "en": "english " + text} if bilingual else text}
        if levels:
            item["Levels"] = {k: ({"de": v, "en": "e " + v} if bilingual else v) for k, v in levels.items()}
        template[code] = item
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"survey-{name}.json"
    path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def libs(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    project = tmp_path / "project"
    project_dir = project / "code" / "library" / "survey"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
    return {"global": global_dir, "project_dir": project_dir, "project": project}


def test_wording_is_compared_without_html_case_or_punctuation():
    assert lwm.normalize_wording("<p>… War ich  bedrückt!</p>") == "war ich bedrückt"


def test_same_wording_with_different_ids_is_exact_and_maps_every_item(libs):
    library_file(libs["global"])

    match = lwm.best_library_match(imported())

    assert match["confidence"] == "exact" and match["adoptable"] is True
    assert match["source"] == "global" and match["template_key"] == "ads"
    assert match["paired"] == match["imported_items"] == match["library_items"] == 4
    assert match["ids_identical"] is False
    assert match["id_map"] == {"ADS1_1": "ads_01", "ADS1_2": "ads_02", "ADS1_3": "ads_03", "ADS1_4": "ads_04"}
    assert match["reworded"] == [] and match["levels_ok"] is True


def test_identical_ids_are_reported_as_identical(libs):
    codes = ["ADS1_1", "ADS1_2", "ADS1_3", "ADS1_4"]
    library_file(libs["global"], codes=codes)

    assert lwm.best_library_match(imported())["ids_identical"] is True


def test_slightly_reworded_items_are_high_not_exact(libs):
    texts = ["war ich sehr bedrückt"] + TEXTS[1:]
    library_file(libs["global"], texts=texts)

    match = lwm.best_library_match(imported())

    assert match["confidence"] == "high" and match["adoptable"] is True
    [reworded] = match["reworded"]
    assert reworded["imported"] == "ADS1_1" and reworded["library"] == "ads_01"
    assert 0.85 <= reworded["similarity"] < 0.97


def test_unrelated_library_template_is_no_match(libs):
    other = ["das Wetter war schön", "wir gingen spazieren", "es gab Kuchen", "am Abend regnete es"]
    library_file(libs["global"], texts=other)

    assert lwm.best_library_match(imported()) is None


def test_partial_coverage_is_medium_and_not_adoptable(libs):
    library_file(libs["global"], texts=TEXTS[:3])

    match = lwm.best_library_match(imported())

    assert match["confidence"] == "medium" and match["adoptable"] is False
    assert match["unpaired_imported"] == ["ADS1_4"]


def test_less_than_seventy_percent_covered_is_no_match(libs):
    library_file(libs["global"], texts=TEXTS[:2])

    assert lwm.best_library_match(imported()) is None


def test_identical_wording_twice_stays_one_to_one_by_position(libs):
    texts = ["ich war müde", "ich war müde", "ich war froh"]
    library_file(libs["global"], texts=texts)

    match = lwm.best_library_match(imported(texts=texts, codes=["a1", "a2", "a3"]))

    assert match["id_map"] == {"a1": "ads_01", "a2": "ads_02", "a3": "ads_03"}


def test_different_answer_levels_cap_the_match_at_medium(libs):
    library_file(libs["global"], levels={"0": "selten", "1": "manchmal"})

    match = lwm.best_library_match(imported())

    assert match["levels_ok"] is False
    assert match["confidence"] == "medium" and match["adoptable"] is False


def test_crossed_ids_are_a_conflict_and_not_adoptable(libs):
    a, b = TEXTS[0], TEXTS[2]
    library_file(libs["global"], texts=[a, b], codes=["Q2", "Q1"])

    match = lwm.best_library_match(imported(texts=[a, b], codes=["Q1", "Q2"]))

    assert match["ids_conflict"] is True
    assert match["confidence"] == "medium" and match["adoptable"] is False


def test_german_import_matches_a_bilingual_library_template(libs):
    library_file(libs["global"], bilingual=True)

    assert lwm.best_library_match(imported())["confidence"] == "exact"


def test_german_import_does_not_match_an_english_only_template(libs):
    english = ["i was depressed", "i was tired", "i could not sleep", "i felt lonely"]
    library_file(libs["global"], texts=english)

    assert lwm.best_library_match(imported()) is None


def test_project_template_wins_over_the_same_global_one(libs):
    library_file(libs["global"])
    library_file(libs["project_dir"])

    assert lwm.best_library_match(imported(), libs["project"])["source"] == "project"


def test_library_with_far_more_items_is_skipped(libs):
    filler = [f"völlig anderer Satz Nummer {i} über etwas ganz anderes" for i in range(6)]
    library_file(libs["global"], texts=TEXTS + filler)

    assert lwm.best_library_match(imported()) is None


def test_missing_folders_and_alias_only_items_do_not_crash(libs):
    assert lwm.best_library_match(imported(), libs["project"] / "nope") is None  # nothing matches

    path = library_file(libs["global"])
    data = json.loads(path.read_text(encoding="utf-8"))
    data["ads_alias"] = {"AliasOf": "ads_01"}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert lwm.best_library_match(imported())["confidence"] == "exact"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_library_wording_match.py -v`
Expected: FAIL — `ImportError: cannot import name 'library_wording_match'`.

- [ ] **Step 3: Implement**

Create `src/converters/library_wording_match.py`:

```python
"""Match an imported questionnaire against the template library by question wording.

Read-only: the global and project libraries are only ever loaded, never written.
"""

from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from src.converters import survey_templates as st

PAIR_THRESHOLD = 0.85
EXACT_THRESHOLD = 0.97
LEVEL_LABEL_THRESHOLD = 0.9
MEDIUM_SHARE = 0.7
_RANK = {"medium": 1, "high": 2, "exact": 3}
_TAG_RE = re.compile(r"<[^>]+>")
_NON_WORD_RE = re.compile(r"[\W_]+")


def normalize_wording(text) -> str:
    """Lowercase letters and digits only, single spaces; HTML and punctuation dropped."""
    text = html.unescape(_TAG_RE.sub(" ", str(text or "")))
    return _NON_WORD_RE.sub(" ", unicodedata.normalize("NFKC", text).lower()).strip()


def similarity(a: str, b: str) -> float:
    """Text similarity in [0, 1]. Below PAIR_THRESHOLD the value is only an upper bound."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    matcher = SequenceMatcher(None, a, b, autojunk=False)
    upper = matcher.quick_ratio()
    return upper if upper < PAIR_THRESHOLD else matcher.ratio()


def _text(value, language: str) -> str:
    if isinstance(value, dict):
        value = st._pick_language_value(value, language) if value else ""
    return normalize_wording(value)


def _items(template: dict) -> list[tuple[str, dict]]:
    """Ordered (code, item) pairs of real items; metadata and alias-only entries skipped."""
    return [
        (key, value)
        for key, value in template.items()
        if key not in st._NON_ITEM_TOPLEVEL_KEYS
        and not st._METADATA_CODE_RE.match(key)
        and isinstance(value, dict)
        and "Description" in value
    ]


def _pair(imp_items, lib_items, language):
    """One-to-one pairing {imported index: (library index, similarity)}, best pairs first."""
    n, m = len(imp_items), len(lib_items)
    imp_texts = [_text(item.get("Description"), language) for _code, item in imp_items]
    lib_texts = [_text(item.get("Description"), language) for _code, item in lib_items]
    candidates = []
    for i, a in enumerate(imp_texts):
        for j, b in enumerate(lib_texts):
            score = similarity(a, b)
            if score >= PAIR_THRESHOLD:
                candidates.append((-score, abs(i / n - j / m), i, j))
    candidates.sort()
    used_lib, pairs = set(), {}
    for negative, _position, i, j in candidates:
        if i in pairs or j in used_lib:
            continue
        pairs[i] = (j, -negative)
        used_lib.add(j)
    return pairs


def _levels_ok(imp_item: dict, lib_item: dict, language: str):
    """True/False when both items have Levels, None when not comparable."""
    imp, lib = imp_item.get("Levels"), lib_item.get("Levels")
    if not isinstance(imp, dict) or not isinstance(lib, dict) or not imp or not lib:
        return None
    if set(imp) != set(lib):
        return False
    for key in imp:
        a, b = _text(imp[key], language), _text(lib[key], language)
        if (a or b) and similarity(a, b) < LEVEL_LABEL_THRESHOLD:
            return False
    return True


def _match_one(imp_items, lib_template: dict, language: str) -> dict | None:
    lib_items = _items(lib_template)
    n, m = len(imp_items), len(lib_items)
    if not n or not m or max(n, m) > 2 * min(n, m):
        return None
    pairs = _pair(imp_items, lib_items, language)
    paired = len(pairs)
    if paired == 0 or paired < MEDIUM_SHARE * n:
        return None

    id_map = {imp_items[i][0]: lib_items[j][0] for i, (j, _score) in pairs.items()}
    lib_keys = {code for code, _item in lib_items}
    ids_conflict = any(imp in lib_keys and imp != lib for imp, lib in id_map.items())
    levels = [_levels_ok(imp_items[i][1], lib_items[j][1], language) for i, (j, _s) in pairs.items()]
    levels_ok = all(result is not False for result in levels)
    scores = [score for _j, score in pairs.values()]
    min_score = min(scores)

    if paired == n == m and min_score >= EXACT_THRESHOLD and levels_ok:
        confidence = "exact"
    elif paired == n and levels_ok:
        confidence = "high"
    else:
        confidence = "medium"
    if ids_conflict and confidence != "medium":
        confidence = "medium"

    paired_lib = {j for j, _s in pairs.values()}
    return {
        "confidence": confidence,
        "paired": paired,
        "imported_items": n,
        "library_items": m,
        "ids_identical": all(imp == lib for imp, lib in id_map.items()),
        "ids_conflict": ids_conflict,
        "adoptable": confidence in ("exact", "high"),
        "levels_ok": levels_ok,
        "mean_similarity": round(sum(scores) / paired, 4),
        "id_map": id_map,
        "reworded": [
            {"imported": imp_items[i][0], "library": lib_items[j][0], "similarity": round(score, 4)}
            for i, (j, score) in sorted(pairs.items())
            if score < EXACT_THRESHOLD
        ],
        "unpaired_imported": [code for i, (code, _item) in enumerate(imp_items) if i not in pairs],
        "unpaired_library": [code for j, (code, _item) in enumerate(lib_items) if j not in paired_lib],
    }


def best_library_match(template: dict, project_path=None) -> dict | None:
    """Best global/project library template for an imported questionnaire, or None."""
    imp_items = _items(template)
    if not imp_items:
        return None
    language = st._default_language_from_template(template)
    candidates = []
    if project_path:
        candidates += [(key, "project", t) for key, t in st._load_project_templates(project_path).items()]
    candidates += [(key, "global", t) for key, t in st._load_global_templates().items()]

    best, best_rank = None, None
    for key, source, tdata in candidates:
        found = _match_one(imp_items, tdata["json"], language)
        if not found:
            continue
        found.update(
            template_key=key,
            source=source,
            template_path=str(tdata["path"]),
            template_file=Path(tdata["path"]).name,
        )
        rank = (_RANK[found["confidence"]], found["mean_similarity"], source == "project")
        if best is None or rank > best_rank:
            best, best_rank = found, rank
    return best
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_library_wording_match.py -v`
Expected: all PASS. If a threshold-edge test fails (the "reworded" similarity or the `medium` partial case), print the actual similarities for the fixture texts before changing code; never loosen a test's expected confidence without telling the controller.

- [ ] **Step 5: Commit**

```bash
git add src/converters/library_wording_match.py tests/test_library_wording_match.py
git commit -m "feat(library-match): pair imported items with library items by wording"
```

---

### Task 2: Adopting a library template (aliases) and the browser-safe view

**Files:**
- Modify: `src/converters/library_wording_match.py`
- Test: `tests/test_library_wording_match.py`

**Interfaces:**
- Consumes: `best_library_match(...)` result (Task 1).
- Produces: `apply_library_template(match: dict | None) -> dict` (raises `ValueError`), `public_library_match(match: dict | None) -> dict | None` (copy without `template_path`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_library_wording_match.py`:

```python
def _tree(directory):
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir())}


def test_adopting_adds_the_survey_codes_as_aliases_and_keeps_library_ids(libs):
    path = library_file(libs["global"])
    match = lwm.best_library_match(imported())

    adopted = lwm.apply_library_template(match)

    assert [k for k in adopted if k.startswith("ads_")] == ["ads_01", "ads_02", "ads_03", "ads_04"]
    assert adopted["ads_01"]["Aliases"] == ["ADS1_1"]
    assert adopted["ads_04"]["Aliases"] == ["ADS1_4"]
    assert "Aliases" not in json.loads(path.read_text(encoding="utf-8"))["ads_01"]  # file untouched


def test_aliases_are_deduplicated_and_identical_codes_get_none(libs):
    path = library_file(libs["global"], codes=["ADS1_1", "ads_02", "ads_03", "ads_04"])
    data = json.loads(path.read_text(encoding="utf-8"))
    data["ads_02"]["Aliases"] = ["ADS1_2"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    adopted = lwm.apply_library_template(lwm.best_library_match(imported()))

    assert "Aliases" not in adopted["ADS1_1"]
    assert adopted["ads_02"]["Aliases"] == ["ADS1_2"]


def test_a_match_that_is_not_one_to_one_cannot_be_adopted(libs):
    library_file(libs["global"], texts=TEXTS[:3])

    with pytest.raises(ValueError, match="one-to-one"):
        lwm.apply_library_template(lwm.best_library_match(imported()))
    with pytest.raises(ValueError, match="one-to-one"):
        lwm.apply_library_template(None)


def test_the_global_library_is_never_written(libs):
    library_file(libs["global"])
    library_file(libs["global"], name="other", texts=["etwas ganz anderes hier", "noch etwas anderes dort"])
    before = _tree(libs["global"])

    match = lwm.best_library_match(imported(), libs["project"])
    lwm.apply_library_template(match)

    assert _tree(libs["global"]) == before


def test_public_view_never_exposes_the_local_path(libs):
    library_file(libs["global"])
    match = lwm.best_library_match(imported())

    public = lwm.public_library_match(match)

    assert "template_path" not in public and public["template_file"] == "survey-ads.json"
    assert public["id_map"] == match["id_map"]
    assert lwm.public_library_match(None) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_library_wording_match.py -v -k "adopt or alias or global_library or public or one_to_one"`
Expected: FAIL — `AttributeError: module ... has no attribute 'apply_library_template'`.

- [ ] **Step 3: Implement**

Append to `src/converters/library_wording_match.py`:

```python
def public_library_match(match: dict | None) -> dict | None:
    """The match as sent to the browser: everything but the local file path."""
    if match is None:
        return None
    return {key: value for key, value in match.items() if key != "template_path"}


def apply_library_template(match: dict | None) -> dict:
    """The matched library template (a copy) with the survey's codes added as ``Aliases``.

    Library IDs stay authoritative. Reads the library file; never writes it.
    """
    if not match or not match.get("adoptable"):
        raise ValueError(
            "The library template does not match every item one-to-one; import the questionnaire as new"
        )
    template = st._read_json(Path(match["template_path"]))
    for imported_code, library_code in match["id_map"].items():
        item = template.get(library_code)
        if imported_code == library_code or not isinstance(item, dict):
            continue
        aliases = item.setdefault("Aliases", [])
        if imported_code not in aliases:
            aliases.append(imported_code)
    return template
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_library_wording_match.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/converters/library_wording_match.py tests/test_library_wording_match.py
git commit -m "feat(library-match): adopt a matched library template with the survey codes as aliases"
```

---

### Task 3: Library match in the LimeSurvey import functions (with terminal log)

**Files:**
- Modify: `src/converters/limesurvey.py` (`list_limesurvey_questionnaires` ≈ l.1380; new functions after `limesurvey_questionnaire_template`)
- Test: `tests/test_limesurvey_library_match.py` (create)

**Interfaces:**
- Consumes: Task 1/2 functions; `limesurvey_questionnaire_template(xml, key, split)` and `_build_questionnaires` from the existing import.
- Produces:
  - `list_limesurvey_questionnaires(xml_content, split="group", source_name="LimeSurvey file", project_path=None, match_library=False)` — with `match_library=True` each entry gains `library_match` (`public_library_match` dict or `None`) and the terminal prints one `[PRISM] Library match for '<name>': ...` line per questionnaire.
  - `match_questionnaire_to_library(template, name, project_path=None) -> dict | None` (logs; never raises).
  - `limesurvey_questionnaire_match(xml_content, key, split="group", project_path=None) -> (template, match)`.
  - `limesurvey_library_template(xml_content, key, split="group", project_path=None) -> (adopted_template, match)`; `ValueError` when not adoptable.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_limesurvey_library_match.py`:

```python
"""LimeSurvey import + library match (spec 2026-10-07-limesurvey-library-match)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.converters import library_wording_match as lwm
from src.converters import limesurvey as ls
from src.converters import survey_templates as st
from test_library_wording_match import library_file

FIXTURE = Path(__file__).parent / "data" / "limesurvey_four_questionnaires.lss"
XML = FIXTURE.read_bytes()
ADS = ["war ich bedrückt", "war ich müde"]
ADS_LEVELS = {"0": "selten", "1": "meistens"}


@pytest.fixture
def libs(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    project = tmp_path / "project"
    (project / "code" / "library" / "survey").mkdir(parents=True)
    monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
    library_file(global_dir, texts=ADS, levels=ADS_LEVELS)
    return {"global": global_dir, "project": project, "project_dir": project / "code" / "library" / "survey"}


def test_matching_is_opt_in():
    assert all("library_match" not in q for q in ls.list_limesurvey_questionnaires(XML))


def test_listing_reports_the_match_per_questionnaire_and_logs_it(libs, capsys):
    found = {q["key"]: q for q in ls.list_limesurvey_questionnaires(XML, match_library=True)}

    ads = found["g30"]["library_match"]
    assert ads["template_key"] == "ads" and ads["confidence"] == "exact" and ads["adoptable"] is True
    assert ads["id_map"] == {"ADS1_1": "ads_01", "ADS1_2": "ads_02"}
    assert "template_path" not in ads
    assert found["g20"]["library_match"] is None
    out = capsys.readouterr().out
    assert "[PRISM] Library match for 'ADS': ads (global) exact — 2/2 items paired, levels equal, IDs differ (ADS1_1->ads_01, ADS1_2->ads_02)" in out
    assert "[PRISM] Library match for 'WHO-5': none" in out


def test_match_for_one_questionnaire_returns_template_and_match(libs):
    template, match = ls.limesurvey_questionnaire_match(XML, "g30")

    assert "ADS1_1" in template and match["template_key"] == "ads"


def test_library_template_carries_the_survey_codes_as_aliases(libs):
    template, match = ls.limesurvey_library_template(XML, "g30")

    assert template["ads_01"]["Aliases"] == ["ADS1_1"] and match["adoptable"] is True


def test_library_template_refuses_when_nothing_matches(libs):
    with pytest.raises(ValueError, match="one-to-one"):
        ls.limesurvey_library_template(XML, "g20")


def test_a_matching_failure_never_blocks_the_import(libs, monkeypatch, capsys):
    def boom(*_a, **_k):
        raise RuntimeError("library unreadable")

    monkeypatch.setattr(lwm, "best_library_match", boom)

    found = ls.list_limesurvey_questionnaires(XML, match_library=True)

    assert len(found) == 4 and all(q["library_match"] is None for q in found)
    assert "[PRISM] Library match skipped: library unreadable" in capsys.readouterr().out


def test_project_library_is_searched_when_a_project_path_is_given(libs):
    for path in libs["global"].iterdir():
        path.unlink()
    library_file(libs["project_dir"], texts=ADS, levels=ADS_LEVELS)

    without = {q["key"]: q for q in ls.list_limesurvey_questionnaires(XML, match_library=True)}
    with_project = {
        q["key"]: q
        for q in ls.list_limesurvey_questionnaires(XML, match_library=True, project_path=libs["project"])
    }

    assert without["g30"]["library_match"] is None
    assert with_project["g30"]["library_match"]["source"] == "project"


def test_a_prism_template_round_trips_to_its_own_library_entry(libs, tmp_path):
    from src.limesurvey_exporter import generate_lss

    texts = ["erstes Item hier", "zweites Item dort"]
    original = {
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "SoftwarePlatform": "LimeSurvey",
                      "Language": "de", "Respondent": "self", "AdministrationMethod": "online"},
        "Study": {"TaskName": "rts", "OriginalName": "Round Trip Scale", "ShortName": "RTS",
                  "Citation": "c", "LicenseID": "CC-BY-4.0", "Category": "other"},
        "RTS01": {"Description": texts[0], "Levels": {"1": "nie", "2": "oft"}},
        "RTS02": {"Description": texts[1], "Levels": {"1": "nie", "2": "oft"}},
    }
    source = libs["project_dir"] / "survey-rts.json"
    source.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    lss = tmp_path / "rts.lss"
    generate_lss([str(source)], output_path=str(lss), language="de")

    [entry] = ls.list_limesurvey_questionnaires(lss.read_bytes(), match_library=True, project_path=libs["project"])

    assert entry["library_match"]["template_key"] == "rts"
    assert entry["library_match"]["confidence"] == "exact"
    assert entry["library_match"]["ids_identical"] is True
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_library_match.py -v`
Expected: FAIL — `TypeError: list_limesurvey_questionnaires() got an unexpected keyword argument 'match_library'`.

- [ ] **Step 3: Implement**

In `src/converters/limesurvey.py`, add after `limesurvey_questionnaire_template` and change `list_limesurvey_questionnaires`:

```python
def _describe_library_match(name, match):
    if not match:
        return f"[PRISM] Library match for '{name}': none"
    changed = [f"{a}->{b}" for a, b in match["id_map"].items() if a != b]
    ids = "IDs identical" if not changed else f"IDs differ ({', '.join(changed[:3])}{', ...' if len(changed) > 3 else ''})"
    levels = "levels equal" if match["levels_ok"] else "levels DIFFER"
    return (
        f"[PRISM] Library match for '{name}': {match['template_key']} ({match['source']}) "
        f"{match['confidence']} — {match['paired']}/{match['imported_items']} items paired, {levels}, {ids}"
    )


def match_questionnaire_to_library(template, name, project_path=None):
    """Best library match for one imported questionnaire; logs, never raises."""
    try:
        from src.converters.library_wording_match import best_library_match

        match = best_library_match(template, project_path)
    except Exception as exc:  # a library problem must not block a plain import
        print(f"[PRISM] Library match skipped: {exc}")
        return None
    print(_describe_library_match(name, match))
    return match


def limesurvey_questionnaire_match(xml_content, key, split="group", project_path=None):
    """(template, library match) for one questionnaire."""
    template = limesurvey_questionnaire_template(xml_content, key, split)
    return template, match_questionnaire_to_library(template, template["Study"]["OriginalName"], project_path)


def limesurvey_library_template(xml_content, key, split="group", project_path=None):
    """(adopted library template with the survey codes as Aliases, match). ValueError if not adoptable."""
    from src.converters.library_wording_match import apply_library_template

    _template, match = limesurvey_questionnaire_match(xml_content, key, split, project_path)
    adopted = apply_library_template(match)
    print(f"[PRISM] Using library template '{match['template_key']}' ({match['source']}): "
          f"{len(match['id_map'])} item code(s) kept as aliases")
    return adopted, match
```

and in `list_limesurvey_questionnaires` add the parameters and, after the existing listing loop (before the final `return`), the matching block. Replace the function with:

```python
def list_limesurvey_questionnaires(
    xml_content, split="group", source_name="LimeSurvey file", project_path=None, match_library=False
):
    """List the questionnaires in a LimeSurvey survey, split by group, question or whole survey.

    With ``match_library`` each entry also gets ``library_match`` (the best global/project
    library template by wording, or None) and the terminal shows one line per questionnaire.
    """
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
    listing = [{k: info[k] for k in ("key", "name", "item_count", "helper")} for info, _ in results]
    if match_library:
        from src.converters.library_wording_match import public_library_match

        for entry, (info, template) in zip(listing, results):
            entry["library_match"] = public_library_match(
                match_questionnaire_to_library(template, info["name"], project_path)
            )
    return listing
```

(Keep the existing body of the listing loop exactly as it is today — only the signature, the `listing` variable and the `if match_library:` block are new; if the current code differs from the snippet above, adapt the snippet to it rather than the reverse.)

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_limesurvey_library_match.py tests/test_limesurvey_questionnaires.py tests/test_library_wording_match.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/converters/limesurvey.py tests/test_limesurvey_library_match.py
git commit -m "feat(limesurvey): opt-in library match for imported questionnaires, logged to the terminal"
```

---

### Task 4: Route — `project_path`, `library_match`, `use_library`

**Files:**
- Modify: `app/src/web/blueprints/tools_template_editor_blueprint.py` (`api_template_editor_import_limesurvey`, ≈ l.583)
- Test: `tests/test_template_editor_import_limesurvey_route.py`

**Interfaces:**
- Consumes: Task 3 functions.
- Produces (same route): form fields `project_path` (optional) and `use_library` (`1`/`true`). List response entries carry `library_match` (or `null`); key call responses carry `library_match`; with `use_library` the `template` is the adopted library template; non-adoptable → `400 {"error": "...one-to-one..."}`. The local library path is never in any response.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_template_editor_import_limesurvey_route.py` (reuse its `_client` and `_post`; add imports `json`, `from src.converters import survey_templates as st`, `from test_library_wording_match import library_file`):

```python
import pytest

ADS = ["war ich bedrückt", "war ich müde"]
ADS_LEVELS = {"0": "selten", "1": "meistens"}


@pytest.fixture
def library(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    project = tmp_path / "project"
    (project / "code" / "library" / "survey").mkdir(parents=True)
    monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
    library_file(project / "code" / "library" / "survey", texts=ADS, levels=ADS_LEVELS)
    return str(project)


def test_list_carries_the_library_match_without_the_local_path(library):
    body = _post(_client(), {"project_path": library}).get_json()

    entries = {q["key"]: q for q in body["questionnaires"]}
    match = entries["g30"]["library_match"]
    assert match["confidence"] == "exact" and match["source"] == "project"
    assert match["id_map"] == {"ADS1_1": "ads_01", "ADS1_2": "ads_02"}
    assert "template_path" not in match and library not in json.dumps(body)
    assert entries["g20"]["library_match"] is None


def test_key_call_returns_the_match_next_to_the_imported_template(library):
    body = _post(_client(), {"project_path": library, "key": "g30"}).get_json()

    assert "ADS1_1" in body["template"]
    assert body["library_match"]["adoptable"] is True


def test_use_library_returns_the_library_template_with_aliases(library):
    body = _post(_client(), {"project_path": library, "key": "g30", "use_library": "1"}).get_json()

    assert body["template"]["ads_01"]["Aliases"] == ["ADS1_1"]
    assert "ADS1_1" not in body["template"]
    assert body["suggested_filename"] == "survey-ads.json"
    assert body["item_count"] == 2


def test_use_library_without_a_one_to_one_match_is_a_400(library):
    response = _post(_client(), {"project_path": library, "key": "g20", "use_library": "1"})

    assert response.status_code == 400
    assert "one-to-one" in response.get_json()["error"]
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_template_editor_import_limesurvey_route.py -v`
Expected: FAIL (`KeyError: 'library_match'`).

- [ ] **Step 3: Implement**

Replace the body of `api_template_editor_import_limesurvey` from the `from src.converters.limesurvey import (...)` line down to the final `return` with:

```python
    project_path = (request.form.get("project_path") or "").strip() or None
    use_library = (request.form.get("use_library") or "").strip().lower() in ("1", "true")

    from src.converters.library_wording_match import public_library_match
    from src.converters.limesurvey import (
        limesurvey_library_template,
        limesurvey_questionnaire_match,
        list_limesurvey_questionnaires,
        read_lss_xml,
    )

    command = f"python prism_tools.py survey import-limesurvey --input {file.filename} --split {split}"
    if project_path:
        command += " --project <project>"
    print(f"[PRISM] CLI equivalent: {command}" + (f" --select {key}{' --use-library' if use_library else ''} --output <dir>" if key else ""))
    try:
        xml = read_lss_xml(file.read(), file.filename)
        if not key:
            questionnaires = list_limesurvey_questionnaires(
                xml, split, source_name=file.filename, project_path=project_path, match_library=True
            )
            return jsonify({"questionnaires": questionnaires, "split": split}), 200
        if use_library:
            template, match = limesurvey_library_template(xml, key, split, project_path)
        else:
            template, match = limesurvey_questionnaire_match(xml, key, split, project_path)
        template = _strip_template_editor_internal_keys(template)
    except ValueError as e:
        print(f"[PRISM] LimeSurvey import failed: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"[PRISM] LimeSurvey import failed: {e}")
        return jsonify({"error": f"Import failed: {e}"}), 500

    i18n = template.get("I18n") or {}
    languages = i18n.get("Languages") or [template.get("Technical", {}).get("Language", "en")]
    reserved = {"Technical", "Study", "Metadata", "I18n", "LimeSurvey", "Scoring", "Normative"}
    return jsonify({
        "template": template,
        "suggested_filename": f"survey-{template['Study']['TaskName']}.json",
        "item_count": len([k for k in template if k not in reserved]),
        "languages": languages,
        "library_match": public_library_match(match),
    }), 200
```

(Keep the existing `file`/`split`/`key` parsing lines above it.)

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_template_editor_import_limesurvey_route.py tests/test_template_editor_import_lsq_lsg_route.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/web/blueprints/tools_template_editor_blueprint.py tests/test_template_editor_import_limesurvey_route.py
git commit -m "feat(template-editor): import-limesurvey route returns the library match and can use the library template"
```

---

### Task 5: CLI — `--project`, `--use-library`, match lines in `--list`

**Files:**
- Modify: `app/src/cli/parser.py` (≈ l.1782–1799), `app/src/cli/commands/survey.py` (`cmd_survey_import_limesurvey` ≈ l.569)
- Test: `tests/test_cli_survey_commands_remaining.py` (class `TestCmdSurveyImportLimesurvey` and helper `_limesurvey_args`)

**Interfaces:**
- Consumes: Task 3 functions.
- Produces: `survey import-limesurvey --input FILE [--split ...] [--list] [--select KEY...|all] [--output DIR] [--project DIR] [--use-library]`. Listing always prints the library match lines (global library + `--project`). `--use-library` (needs `--select`) writes the adopted library template as `survey-<TaskName>.json`; exit 1 with the `one-to-one` message for a key without an adoptable match; `--use-library` without `--select` is an error.

- [ ] **Step 1: Write the failing tests**

In `tests/test_cli_survey_commands_remaining.py` extend `_limesurvey_args` defaults with `project=None, use_library=False`, add `import json`/`st`/`library_file` imports, and append tests to the class:

```python
    @pytest.fixture
    def library(self, tmp_path, monkeypatch):
        from src.converters import survey_templates as st
        from test_library_wording_match import library_file

        global_dir = tmp_path / "global"
        global_dir.mkdir()
        project = tmp_path / "project"
        (project / "code" / "library" / "survey").mkdir(parents=True)
        monkeypatch.setattr(st, "_load_global_library_path", lambda: global_dir)
        library_file(global_dir, texts=["war ich bedrückt", "war ich müde"], levels={"0": "selten", "1": "meistens"})
        return {"global": global_dir, "project": project}

    def test_list_shows_the_library_match_lines(self, library, capsys):
        cmd_survey_import_limesurvey(_limesurvey_args())

        out = capsys.readouterr().out
        assert "Library match for 'ADS': ads (global) exact" in out
        assert "Library match for 'WHO-5': none" in out

    def test_use_library_writes_the_library_template_with_aliases_and_leaves_the_global_folder_alone(
        self, library, tmp_path
    ):
        before = {p.name: p.read_bytes() for p in library["global"].iterdir()}
        out_dir = tmp_path / "out"

        cmd_survey_import_limesurvey(_limesurvey_args(select=["g30"], use_library=True, output=str(out_dir)))

        written = json.loads((out_dir / "survey-ads.json").read_text(encoding="utf-8"))
        assert written["ads_01"]["Aliases"] == ["ADS1_1"]
        assert {p.name: p.read_bytes() for p in library["global"].iterdir()} == before

    def test_use_library_refuses_a_questionnaire_without_an_exact_or_high_match(self, library, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cmd_survey_import_limesurvey(
                _limesurvey_args(select=["g20"], use_library=True, output=str(tmp_path / "out"))
            )

        assert exc_info.value.code == 1
        assert "one-to-one" in capsys.readouterr().out

    def test_use_library_needs_select(self, library, capsys):
        with pytest.raises(SystemExit):
            cmd_survey_import_limesurvey(_limesurvey_args(use_library=True))
        assert "--use-library needs --select" in capsys.readouterr().out

    def test_project_library_is_included_with_project(self, library, tmp_path, capsys):
        from test_library_wording_match import library_file

        for p in library["global"].iterdir():
            p.unlink()
        library_file(library["project"] / "code" / "library" / "survey", texts=["war ich bedrückt", "war ich müde"],
                     levels={"0": "selten", "1": "meistens"})

        cmd_survey_import_limesurvey(_limesurvey_args(project=str(library["project"])))

        assert "ads (project) exact" in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_cli_survey_commands_remaining.py -k ImportLimesurvey -v`
Expected: FAIL (listing prints no library lines; `--use-library` unknown).

- [ ] **Step 3: Implement**

`app/src/cli/parser.py` — after the `--output` argument of `import-limesurvey` add:

```python
    parser_survey_limesurvey.add_argument(
        "--project", help="Project folder whose library (code/library/survey) is also searched for a matching template"
    )
    parser_survey_limesurvey.add_argument(
        "--use-library", action="store_true",
        help="With --select: write the matching library template (survey codes kept as Aliases) "
        "instead of the imported questionnaire; only for exact/high matches",
    )
```

`app/src/cli/commands/survey.py` — in `cmd_survey_import_limesurvey` import `limesurvey_library_template`, add the validation, pass the project path and match flag to the listing, and use the library template when asked:

```python
    from src.converters.limesurvey import (
        limesurvey_library_template,
        limesurvey_questionnaire_template,
        list_limesurvey_questionnaires,
        read_lss_xml,
    )

    input_path = Path(args.input).resolve()
    project_path = getattr(args, "project", None)
    use_library = bool(getattr(args, "use_library", False))
    try:
        if args.output and not args.select:
            raise ValueError("--output needs --select KEY|all (use --list to see the keys)")
        if use_library and not args.select:
            raise ValueError("--use-library needs --select KEY|all")
        xml = read_lss_xml(input_path.read_bytes(), input_path.name)
        found = list_limesurvey_questionnaires(
            xml, args.split, source_name=input_path.name, project_path=project_path, match_library=True
        )
        ...  # unchanged: --list handling, --output check, keys, out_dir
        for key in keys:
            if use_library:
                template, _match = limesurvey_library_template(xml, key, args.split, project_path)
            else:
                template = limesurvey_questionnaire_template(xml, key, args.split)
            ...  # unchanged: target path, overwrite refusal, write
```

(Keep every unchanged line exactly as in the current function; only the highlighted additions change.)

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cli_survey_commands_remaining.py tests/test_prism_tools_cli_contract.py tests/test_cli_dispatch_routing.py -v`
Then `.venv/bin/python prism_tools.py survey import-limesurvey --input tests/data/limesurvey_four_questionnaires.lss` (prints the listing plus one `Library match` line per questionnaire against the real global library, read-only).
Expected: tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/cli/parser.py app/src/cli/commands/survey.py tests/test_cli_survey_commands_remaining.py
git commit -m "feat(cli): import-limesurvey shows library matches and can write the library template (--use-library)"
```

---

### Task 6: Editor — match in the picker, card with ID table, "Use library template"

**Files:**
- Create: `app/static/js/template-editor/library-match-card.js`, `app/static/js/template-editor/library-match-card.test.js`
- Modify: `app/templates/template_editor.html` (card container after the picker `form-text`, ≈ l.100), `app/static/js/template-editor.js` (element lookup + context, next to `sourceSplitSelectEl`), `app/static/js/template-editor/source-workflow.js` (`fetchLimeSurvey`, `loadLimeSurveyQuestionnaire`, `importLimeSurvey`, `hideExcelGroupPicker`)
- Test: `tests/e2e/test_template_editor_flows.py`

**Interfaces:**
- Consumes: Task 4 route (`library_match` in list entries and key responses; `use_library=1`; `project_path`).
- Produces: `libraryMatchSummary(match) -> string`, `renderLibraryMatchCard(match, escapeHtml) -> html string` (buttons carry `data-action="use-library"` and `data-action="import-new"`; `use-library` only when `match.adoptable`); DOM `#libraryMatchCard`; context field `libraryMatchCardEl`.

- [ ] **Step 1: Write the failing tests**

`app/static/js/template-editor/library-match-card.test.js`:

```js
import { describe, expect, it } from 'vitest';

import { libraryMatchSummary, renderLibraryMatchCard } from './library-match-card.js';

const escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const EXACT = {
    template_key: 'ads', source: 'global', confidence: 'exact', paired: 2, imported_items: 2, library_items: 2,
    ids_identical: false, ids_conflict: false, adoptable: true, levels_ok: true, reworded: [],
    id_map: { ADS1_1: 'ads_01', ADS1_2: 'ads_02' }, unpaired_imported: [], unpaired_library: [],
};
const PARTIAL = { ...EXACT, confidence: 'medium', adoptable: false, paired: 1, unpaired_imported: ['ADS1_2'], unpaired_library: [] };

describe('libraryMatchSummary', () => {
    it('names the template, where it lives and how well it fits', () => {
        expect(libraryMatchSummary(EXACT)).toBe('match: ads (global, exact)');
        expect(libraryMatchSummary(null)).toBe('');
    });
});

describe('renderLibraryMatchCard', () => {
    it('offers the library template for an exact match and lists the ID mapping', () => {
        const html = renderLibraryMatchCard(EXACT, escapeHtml);
        expect(html).toContain('wording identical');
        expect(html).toContain('levels identical');
        expect(html).toContain('item IDs differ');
        expect(html).toContain('data-action="use-library"');
        expect(html).toContain('data-action="import-new"');
        expect(html).toContain('ADS1_1');
        expect(html).toContain('ads_01');
    });

    it('shows a partial match as information only', () => {
        const html = renderLibraryMatchCard(PARTIAL, escapeHtml);
        expect(html).not.toContain('data-action="use-library"');
        expect(html).toContain('data-action="import-new"');
        expect(html).toContain('1 imported item(s) without a match');
    });

    it('says how many items were reworded and escapes codes', () => {
        const html = renderLibraryMatchCard(
            { ...EXACT, confidence: 'high', reworded: [{ imported: '<b>x', library: 'y', similarity: 0.9 }], id_map: { '<b>x': 'y' } },
            escapeHtml,
        );
        expect(html).toContain('1 item(s) reworded');
        expect(html).toContain('&lt;b&gt;x');
        expect(html).not.toContain('<b>x');
    });

    it('renders nothing without a match', () => {
        expect(renderLibraryMatchCard(null, escapeHtml)).toBe('');
    });
});
```

In `tests/e2e/test_template_editor_flows.py` append (the `project` fixture is the throwaway project root; if its return value is not a `Path`, adapt the first line only):

```python
import json


def put_ads_in_project_library(project):
    template = {
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "SoftwarePlatform": "LimeSurvey",
                      "Language": "de", "Respondent": "self", "AdministrationMethod": "online"},
        "Study": {"TaskName": "ads", "OriginalName": "ADS", "Citation": "c", "LicenseID": "CC-BY-4.0", "Category": "other"},
        "ads_01": {"Description": "war ich bedrückt", "Levels": {"0": "selten", "1": "meistens"}},
        "ads_02": {"Description": "war ich müde", "Levels": {"0": "selten", "1": "meistens"}},
    }
    (project / "code" / "library" / "survey" / "survey-ads.json").write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")


def pick_ads(page):
    page.click("#btnCreateOpen")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    page.select_option("#excelGroupPickerSelect", "g30")


def test_library_match_is_shown_and_the_library_template_can_be_used(page, project):
    put_ads_in_project_library(project)
    pick_ads(page)

    expect(page.locator('#excelGroupPickerSelect option[value="g30"]')).to_contain_text("match: ads (project, exact)")
    card = page.locator("#libraryMatchCard")
    expect(card).to_be_visible()
    expect(card).to_contain_text("item IDs differ")
    assert page.evaluate(CONTRAST_JS.replace("#alertArea .error-link code", "#libraryMatchCard .lib-match-title")) >= 4.5

    page.click('#libraryMatchCard [data-action="use-library"]')

    expect(page.locator('option[value="ads_01"]')).to_have_count(1)
    expect(page.locator('option[value="ADS1_1"]')).to_have_count(0)


def test_import_as_new_keeps_the_survey_items(page, project):
    put_ads_in_project_library(project)
    pick_ads(page)

    page.click('#libraryMatchCard [data-action="import-new"]')

    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)


def test_questionnaire_without_a_match_shows_no_card(page, project):
    put_ads_in_project_library(project)
    page.click("#btnCreateOpen")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    page.select_option("#excelGroupPickerSelect", "g20")

    expect(page.locator("#libraryMatchCard")).to_be_hidden()
```

(The contrast helper `CONTRAST_JS` already exists in this file; its selector pair is replaced via `str.replace`, so the card needs a `.lib-match-title` element inside an element with a solid background colour, see Step 3. If the helper's `.closest('.alert')` lookup does not suit the card, give the card the class `alert` — see the markup below.)

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run app/static/js/template-editor/library-match-card.test.js` — FAIL (module missing).
Run: `.venv/bin/python -m pytest tests/e2e/test_template_editor_flows.py -k "library or import_as_new or without_a_match" -v` — FAIL (no card).

- [ ] **Step 3: Implement**

`app/static/js/template-editor/library-match-card.js`:

```js
export function libraryMatchSummary(match) {
  if (!match) {
    return '';
  }
  return `match: ${match.template_key} (${match.source}, ${match.confidence})`;
}

export function renderLibraryMatchCard(match, escapeHtml) {
  if (!match) {
    return '';
  }
  const wording = match.reworded.length === 0 ? 'wording identical' : `${match.reworded.length} item(s) reworded`;
  const levels = match.levels_ok ? 'levels identical' : 'levels differ';
  const ids = match.ids_identical ? 'item IDs identical' : 'item IDs differ';
  const notes = [];
  if (match.unpaired_imported.length) {
    notes.push(`${match.unpaired_imported.length} imported item(s) without a match`);
  }
  if (match.unpaired_library.length) {
    notes.push(`${match.unpaired_library.length} library item(s) not in your survey`);
  }
  if (match.ids_conflict) {
    notes.push('an imported ID is already used by a different library item');
  }
  const changed = Object.entries(match.id_map).filter(([imported, library]) => imported !== library);
  const rows = changed
    .map(([imported, library]) => `<tr><td><code>${escapeHtml(imported)}</code></td><td><code>${escapeHtml(library)}</code></td></tr>`)
    .join('');
  const table = rows
    ? `<details class="mt-1"><summary>Item ID mapping (${changed.length})</summary>`
      + `<table class="table table-sm mb-0"><thead><tr><th>Your survey</th><th>Library</th></tr></thead><tbody>${rows}</tbody></table></details>`
    : '';
  const useButton = match.adoptable
    ? '<button type="button" class="btn btn-sm btn-success me-1" data-action="use-library">Use library template</button>'
    : '';
  return `<div class="lib-match-title fw-semibold">Library match: ${escapeHtml(match.template_key)} (${escapeHtml(match.source)}, ${escapeHtml(match.confidence)})</div>`
    + `<div>${match.paired}/${match.imported_items} items paired &middot; ${wording} &middot; ${levels} &middot; ${ids}</div>`
    + (notes.length ? `<div>${notes.map(escapeHtml).join(' &middot; ')}</div>` : '')
    + table
    + `<div class="mt-2">${useButton}<button type="button" class="btn btn-sm btn-outline-secondary" data-action="import-new">Import as new</button></div>`;
}
```

`template_editor.html` — inside `#excelGroupPickerRow`, after the `form-text` div:

```html
              <div class="alert alert-success mt-2 mb-0 py-2 d-none" id="libraryMatchCard"></div>
```

`template-editor.js` — next to `const sourceSplitSelectEl = ...` add `const libraryMatchCardEl = document.getElementById('libraryMatchCard');` and pass `libraryMatchCardEl,` in the source-workflow context beside `sourceSplitSelectEl,`.

`source-workflow.js`:
1. `import { libraryMatchSummary, renderLibraryMatchCard } from './library-match-card.js';` at the top.
2. `hideExcelGroupPicker`: also `if (context.libraryMatchCardEl) { context.libraryMatchCardEl.classList.add('d-none'); context.libraryMatchCardEl.innerHTML = ''; }`.
3. `loadLimeSurveyQuestionnaire(context, file, key, previousEditorState, useLibrary = false)`: fields become `{ split: context.sourceSplitSelectEl.value, key, project_path: context.getCurrentProjectPath() || '', ...(useLibrary ? { use_library: '1' } : {}) }`.
4. `importLimeSurvey`: list call also sends `project_path: context.getCurrentProjectPath() || ''`; keep `questionnaires`; option text gets `${q.library_match ? ` · ${libraryMatchSummary(q.library_match)}` : ''}`; add
```js
  const showCard = () => {
    const entry = questionnaires.find((q) => q.key === context.excelGroupPickerSelectEl.value);
    const html = renderLibraryMatchCard(entry && entry.library_match, context.escapeHtml);
    context.libraryMatchCardEl.innerHTML = html;
    context.libraryMatchCardEl.classList.toggle('d-none', !html);
  };
  context.excelGroupPickerSelectEl.onchange = showCard;
  context.libraryMatchCardEl.onclick = (event) => {
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (!action) {
      return;
    }
    if (context.hasUnsavedChanges() && !confirm('You have unsaved changes. Loading this questionnaire will discard them. Continue?')) {
      return;
    }
    loadLimeSurveyQuestionnaire(context, file, context.excelGroupPickerSelectEl.value, context.captureEditorState(), action === 'use-library');
  };
  showCard();
```
   (call `showCard()` after the preselect line; the single-questionnaire direct load stays as it is).

If the card background/text fails the contrast check, fix it in `studio-theme.css` for `.alert-success` text colour, not with inline styles.

- [ ] **Step 4: Run tests**

Run: `npx vitest run` — all PASS.
Run: `.venv/bin/python -m pytest tests/e2e/test_template_editor_flows.py tests/test_template_editor_workflow_wiring.py -v` — all PASS (Chromium must run; say so if skipped).

- [ ] **Step 5: Commit**

```bash
git add app/static/js/template-editor app/templates/template_editor.html app/static/js/template-editor.js app/static/css/studio-theme.css tests/e2e/test_template_editor_flows.py
git commit -m "feat(template-editor): show the library match for an imported questionnaire and offer the library template"
```

---

### Task 7: Docs, real-survey check, full suite

**Files:**
- Modify: `docs/CLI_REFERENCE.md` (the `import-limesurvey` section ≈ l.193–205), `docs/LIMESURVEY_INTEGRATION.md` (the import section ≈ l.280)

- [ ] **Step 1:** In `docs/CLI_REFERENCE.md` document `--project DIR` and `--use-library` (one short paragraph + one example: `... --select g30 --use-library --output ./templates`), and that listing prints a library match per questionnaire (global library, plus the project's with `--project`). In `docs/LIMESURVEY_INTEGRATION.md` add 3–5 lines under the import steps: the match card, "Use library template" vs "Import as new", that item IDs of the library are kept and the survey's codes are stored as aliases, and that nothing is ever written to the global library.

- [ ] **Step 2:** Read-only check on the real survey and the real global library (output to the scratchpad only):
`.venv/bin/python prism_tools.py survey import-limesurvey --input .venv/survey_archive_939812.lsa` — paste the `Library match` lines in the report. Then `git status --short` must show nothing under the repo's global library folder.

- [ ] **Step 3:** `.venv/bin/python -m pytest -q -p no:cacheprovider` and `npx vitest run`. Expected: only the three known failures (`test_accepts_symlinked_pair`, `test_fake_environment_package_is_gone`, `e2e/test_validate_flows.py::test_an_empty_project_says_there_is_no_data_instead_of_passing`); report any other failure verbatim.

- [ ] **Step 4:** Commit the docs: `git add docs && git commit -m "docs: library match for LimeSurvey imports"`.
