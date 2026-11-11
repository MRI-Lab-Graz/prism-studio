# Survey Term IDs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every instrument, item and score of the official survey library has a frozen `prism:` ID, and a project's survey sidecar column can be resolved to it.

**Architecture:** One new backend module derives a term registry (the dict shape `load_registry` returns) from the library templates and the recipes; nothing is stored per item. A committed list of released IDs makes them frozen. The `terms` CLI reads that registry for `--modality survey` and gets a `resolve` action. No Studio page, no validator change.

**Tech Stack:** Python stdlib, pytest. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-11-term-ids-all-modalities-design.md` (section "Step 2").

## Global Constraints

- Instrument `prism:<taskname>`; item `prism:<taskname>.<item-key>`; score `prism:<taskname>.score-<score-name>`.
- `<item-key>`: the template key lowercased, `_` written as `-`. `<score-name>`: the recipe's `Name` lowercased, `_` as `-`, without a leading `<taskname>-`.
- Every local segment must match `[a-z][a-z0-9-]{0,62}`; `score-` is reserved (an item key that starts with it is an error).
- `Level` is `instrument`, `item` or `score`.
- A template without a recipe gives instrument and item IDs; a recipe without a template gives no IDs and is reported.
- An edited project item (answer scale or wording) has no official ID. Nothing is written into a sidecar. The validator's verdict does not change.
- A released ID never disappears: the released-ID list only grows, by a command, never by hand.
- `load_registry()` is not changed (the validator calls it for modalities that declare terms; survey must stay out of that).
- Logic in `src/`, exposed by `prism_tools.py terms`; nothing in `app/src/web/**`.
- Library and project files are untrusted data: a bad file or type is a message, never a traceback.
- Not in this plan: the optional item field `DerivedFrom` (short forms). It is a survey schema change in prism-specification, no library item needs it today, and it gets its own small pull request there.
- Pull request A = Tasks 1 to 3, pull request B = Task 4. Before each merge: `/ponytail:ponytail-audit`, `/code-review`.

## Review Focus

1. A template that is unreadable or not a JSON object: skipped and reported, the rest of the library still gets IDs (Task 1).
2. An item key or score name that gives no valid slug (space, umlaut, leading digit): reported, no ID, no crash (Task 1).
3. Two templates with the same `Study.TaskName`: the second is reported and ignored (Task 1).
4. A project sidecar whose `Study` is missing or not an object: every column "unknown instrument", no crash (Task 4).
5. A project item whose text is a plain string in a language the library does not have: it resolves (a translation is the same item) (Task 4).

---

### Task 1: Derive the survey term registry

**Files:**
- Create: `src/survey_terms.py`
- Test: `tests/test_survey_terms.py`

**Interfaces:**
- Consumes: `src.term_registry.terms_root()` (`official/library/terms`; the survey library is `terms_root().parent / "survey"`, the recipes `terms_root().parents[1] / "recipe" / "survey"`).
- Produces:
  - `item_local_id(task: str, key: str) -> str` (`"tipi", "TIPI02"` -> `"tipi.tipi02"`)
  - `score_local_id(task: str, name: str) -> str` (`"tipi", "tipi_extraversion"` -> `"tipi.score-extraversion"`)
  - `build_survey_registry(library_dir: Path | None = None, recipe_dir: Path | None = None) -> tuple[dict[str, dict], list[str]]`: (local ID -> term, problems).
  - Term shapes: instrument `{"TermID", "Level": "instrument", "Label": Study.ShortName or the task name, "Description": Study.OriginalName (en, else the first value, else ""), "Status": "official"}`; item `{"TermID", "Level": "item", "Parent": "prism:<task>", "Label": the template key as written, "Description": the item text (en, else first, else ""), "Status": "official"}`; score `{"TermID", "Level": "score", "Parent": "prism:<task>", "Label": "<instrument Label> <recipe Name>", "Description": the score's Description or "", "Status": "official"}`.
  - Rules: templates are `survey-*.json` (a stem containing `participant` is skipped, as `instrument_registry.py` does); task = `Study.TaskName` or the stem without `survey-`; items are the top-level keys other than `Technical`, `Metadata`, `I18n`, `Study`, `Normative` whose value is an object without `AliasOf`; recipes are `recipe-<task>.json`, scores their `Scores[].Name`.

- [ ] **Step 1: Write the failing tests** (`tmp_path` libraries built by a small helper `_lib(tmp_path, templates: dict, recipes: dict)`)

```python
def test_ids_follow_the_agreed_shape():
    assert item_local_id("tipi", "TIPI02") == "tipi.tipi02"
    assert item_local_id("ads-k", "ADS_K01") == "ads-k.ads-k01"
    assert score_local_id("tipi", "tipi_extraversion") == "tipi.score-extraversion"
    assert score_local_id("tipi", "Total") == "tipi.score-total"

def test_registry_has_instrument_items_and_scores(tmp_path):
    reg, problems = build_survey_registry(*_lib(tmp_path, {"tipi": TIPI}, {"tipi": {"Scores": [{"Name": "Total", "Items": ["TIPI01"]}]}}))
    assert problems == []
    assert reg["tipi"]["Level"] == "instrument" and reg["tipi"]["TermID"] == "prism:tipi"
    assert reg["tipi.tipi01"] == {"TermID": "prism:tipi.tipi01", "Level": "item", "Parent": "prism:tipi",
                                  "Label": "TIPI01", "Description": "Extraverted, enthusiastic", "Status": "official"}
    assert reg["tipi.score-total"]["Level"] == "score" and reg["tipi.score-total"]["Label"] == "TIPI Total"

def test_template_without_recipe_still_gets_ids(tmp_path):        # no score-* keys, problems == []
def test_recipe_without_template_gets_no_ids_and_is_reported(tmp_path):   # reg == {}, "psqi" in problems[0]
def test_alias_items_get_no_id(tmp_path):                         # {"AliasOf": "TIPI01"} is not in reg
def test_bad_files_and_names_are_reported_not_raised(tmp_path):
    # Review Focus 1-3: a template holding "[1]", one with invalid JSON, an item key "Frage 1", an item key
    # "score-x", a score Name "Ärger", two templates with TaskName "tipi":
    # each gives exactly one problem naming the file or key, none gives an ID, the good template keeps all its IDs.

def test_shipped_library_gives_every_item_and_score_an_id():
    reg, problems = build_survey_registry()
    assert all("no library template" in p for p in problems)      # today: psqi
    levels = collections.Counter(t["Level"] for t in reg.values())
    assert levels["instrument"] == 103 and levels["item"] == 1268 and levels["score"] >= 100
    assert all(key == t["TermID"].partition(":")[2] for key, t in reg.items())
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_survey_terms.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement the three functions in `src/survey_terms.py`.** Confirm afterwards with `python -c "import src.survey_terms as m; print(m.__file__)"` that the file under top-level `src/` answers (dual-tree rule) and that no `app/src/survey_terms.py` exists.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(terms): survey term registry derived from the library templates and recipes`.

### Task 2: Released IDs are frozen, one ID names one concept

**Files:**
- Modify: `src/survey_terms.py`
- Create: `official/library/survey/term-ids.txt` (written by the command of Task 3, committed)
- Test: `tests/test_survey_terms.py`

**Interfaces:**
- Consumes: `build_survey_registry` (Task 1); the vendored `scripts/specification/check_terms.py::cross_registry_problems(registries: dict[str, dict]) -> list[str]`, loaded the way `tests/test_check_terms.py` loads it.
- Produces:
  - `released_ids(path: Path | None = None) -> set[str]` (default `official/library/survey/term-ids.txt`; a missing file is an empty set; blank lines ignored)
  - `freeze_problems(registry: dict[str, dict], released: set[str]) -> list[str]`: one line per released ID that the registry no longer has: `"<TermID>: released ID is gone (an ID is frozen; restore the item, score or task name)"`
  - `write_released_ids(registry: dict[str, dict], path: Path | None = None) -> list[str]`: writes the sorted union of the file's IDs and the registry's `TermID`s, one per line; returns the IDs that were added. It never removes a line.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_released_id_that_disappears_is_a_problem():
    assert freeze_problems({"tipi": {"TermID": "prism:tipi"}}, {"prism:tipi", "prism:tipi.tipi01"}) == [
        "prism:tipi.tipi01: released ID is gone (an ID is frozen; restore the item, score or task name)"]

def test_write_released_ids_only_adds(tmp_path):
    path = tmp_path / "ids.txt"; path.write_text("prism:old\n", encoding="utf-8")
    assert write_released_ids({"tipi": {"TermID": "prism:tipi"}}, path) == ["prism:tipi"]
    assert path.read_text(encoding="utf-8") == "prism:old\nprism:tipi\n"
    assert write_released_ids({"tipi": {"TermID": "prism:tipi"}}, path) == []

def test_shipped_released_ids_are_all_still_there():
    reg, _ = build_survey_registry()
    released = released_ids()
    assert released and freeze_problems(reg, released) == []

def test_no_survey_id_exists_in_another_modality():
    reg, _ = build_survey_registry()
    assert check_terms.cross_registry_problems(
        {"biosample": load_registry("biosample"), "environment": load_registry("environment"), "survey": reg}) == []
```

- [ ] **Step 2: Run.** Expected: FAIL (functions missing; `test_shipped_released_ids_are_all_still_there` fails on the empty set until Task 3 writes the file).
- [ ] **Step 3: Implement the three functions.**
- [ ] **Step 4: Run.** Expected: PASS except `test_shipped_released_ids_are_all_still_there` (passes after Task 3 Step 5).
- [ ] **Step 5: Commit** `feat(terms): released survey IDs are frozen; no survey ID in another modality`.

### Task 3: `terms list|show|freeze --modality survey`

**Files:**
- Modify: `app/src/cli/commands/terms.py`, `app/src/cli/parser.py` (the `terms` block, about line 2195), the dispatch table that maps `terms` actions to `cmd_terms_*` (find it with `grep -rn cmd_terms_show app/src/cli`), `docs/CLI_REFERENCE.md` (section `## terms`)
- Test: `tests/test_cli_terms.py`

**Interfaces:**
- Consumes: `build_survey_registry`, `write_released_ids`, `freeze_problems`, `released_ids` (Tasks 1, 2); `term_links` (already used by `show`).
- Produces: in `terms.py` one helper `_registry(modality: str) -> dict[str, dict]` (`build_survey_registry()[0]` for `"survey"`, else `load_registry(modality)`), used by `cmd_terms_list` and `cmd_terms_show`; `cmd_terms_freeze(args)`.
- `terms freeze --modality survey [--json]`: prints the registry's problems and the freeze problems; when there is a freeze problem it writes nothing and exits 1; otherwise it calls `write_released_ids` and prints `added N ID(s)`; exit 0. Any other `--modality` exits 1 with `Error: only the survey registry is frozen this way`.
- `list` for survey prints the same four tab-separated columns (`TermID`, `Level`, `Label`, `Status`).

- [ ] **Step 1: Write the failing tests**

```python
def test_terms_list_survey_shows_instrument_item_and_score():
    code, out = _run("list", "--modality", "survey")
    assert code == 0 and "prism:tipi\tinstrument" in out and "prism:tipi.tipi02\titem" in out and "prism:tipi.score-total\tscore" in out

def test_terms_show_survey_item_by_id_and_by_its_key():
    for name in ("prism:tipi.tipi02", "TIPI02"):
        code, out = _run("show", name, "--modality", "survey", "--json")
        assert code == 0 and json.loads(out)["term"]["Parent"] == "prism:tipi"

def test_terms_freeze_is_for_survey_only():
    code, out = _run("freeze", "--modality", "biosample")
    assert code == 1 and "only the survey registry" in out

def test_terms_freeze_on_the_shipped_library_adds_nothing():       # after Step 5: code 0, "added 0 ID(s)"
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the helper, `cmd_terms_freeze`, the `freeze` sub-parser and its dispatch entry.
- [ ] **Step 4: Run** `tests/test_cli_terms.py tests/test_survey_terms.py`. Expected: PASS except the two shipped-list tests.
- [ ] **Step 5: Write the released list**: `.venv/bin/python prism_tools.py terms freeze --modality survey`; check `wc -l official/library/survey/term-ids.txt` is 103 + 1268 + the number of scores; run both test files. Expected: all PASS. Also run every test that globs `official/library/survey` (`grep -rln "library/survey" tests | xargs .venv/bin/python -m pytest -q`): the new `.txt` must break none.
- [ ] **Step 6: Document** `freeze` and `--modality survey` in `docs/CLI_REFERENCE.md`; commit `feat(terms): terms list|show|freeze for the survey registry; first released survey IDs`. Open pull request A.

### Task 4: Resolve a project sidecar's columns (`terms resolve`)

**Files:**
- Modify: `src/survey_terms.py`, `app/src/cli/commands/terms.py`, `app/src/cli/parser.py`, the dispatch table, `docs/CLI_REFERENCE.md`
- Test: `tests/test_survey_terms.py`, `tests/test_cli_terms.py`

**Interfaces:**
- Consumes: `build_survey_registry`, `item_local_id` (Task 1).
- Produces: `resolve_survey_sidecar(sidecar: dict, library_dir: Path | None = None, recipe_dir: Path | None = None) -> dict`:
  `{"instrument": TermID | None, "columns": [{"column": str, "term": TermID | None, "reason": str}]}`; one entry per top-level key other than `Technical`, `Metadata`, `I18n`, `Study`, `Normative`; `reason` is `""` when `term` is set, else exactly one of `unknown instrument`, `unknown item`, `alias`, `changed scale`, `changed wording`.
- Rules, checked in this order: `Study.TaskName` is not a library instrument -> `unknown instrument` for every column. The column is not an item of that template (exact key) -> `unknown item`. The column has `AliasOf` -> `alias`. **Scale**: the set of `Levels` keys differs from the library item's, or the sidecar sets `MinValue`/`MaxValue` (not `None`) to another number -> `changed scale`; a library item with `VariantScales` also accepts each variant's `Levels`/`MinValue`/`MaxValue`. **Wording**: compare `Description` per language that both sides have, after collapsing whitespace (`" ".join(text.split())`), case-sensitive; a plain string on the sidecar side is in `Technical.Language`; any difference -> `changed wording`; a language the library does not have is not compared.
- CLI: `terms resolve --sidecar <file> [--json]`. Text: one line per column `<column>\t<TermID or ->\t<reason>`. JSON: `{"success": true, "instrument": ..., "columns": [...]}`. Exit 0 when the file was read, 1 with `Error: ...` when it is missing, not JSON or not an object.

- [ ] **Step 1: Write the failing tests**

```python
def test_an_unchanged_item_resolves_to_its_official_id(tmp_path):
    out = resolve_survey_sidecar({"Study": {"TaskName": "tipi"}, "Technical": {"Language": "en"}, "TIPI01": dict(TIPI["TIPI01"])}, *LIB)
    assert out == {"instrument": "prism:tipi", "columns": [{"column": "TIPI01", "term": "prism:tipi.tipi01", "reason": ""}]}

@pytest.mark.parametrize("change,reason", [
    ({"Levels": {"1": "a", "2": "b"}}, "changed scale"),
    ({"MaxValue": 99}, "changed scale"),
    ({"Description": {"en": "Something else"}}, "changed wording"),
    ({"Description": "Something else"}, "changed wording"),          # plain string, Technical.Language en
    ({"AliasOf": "TIPI02"}, "alias"),
])
def test_an_edited_item_loses_the_official_id(tmp_path, change, reason): ...

def test_same_text_with_other_whitespace_and_a_missing_min_max_still_resolve(tmp_path): ...
def test_a_translation_the_library_lacks_still_resolves(tmp_path):   # Review Focus 5: Description {"fr": "..."}
def test_unknown_item_and_unknown_instrument(tmp_path): ...
def test_study_missing_or_not_an_object_is_unknown_instrument(tmp_path):   # Review Focus 4: {}, {"Study": []}
def test_a_variant_scale_of_the_library_item_is_accepted(tmp_path): ...

def test_terms_resolve_cli(tmp_path):
    # a copy of official/library/survey/survey-tipi.json with one item's MaxValue changed:
    # code 0; "TIPI01\tprism:tipi.tipi01\t" in out; the changed item's line ends with "-\tchanged scale"
def test_terms_resolve_bad_file_exits_1(tmp_path):                  # missing file, "[1]", "{": code 1, "Error:" in out, no traceback
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement `resolve_survey_sidecar`, `cmd_terms_resolve`, the `resolve` sub-parser and its dispatch entry.**
- [ ] **Step 4: Run** `tests/test_survey_terms.py tests/test_cli_terms.py tests/test_term_registry.py`. Expected: PASS.
- [ ] **Step 5: Document** `resolve` in `docs/CLI_REFERENCE.md`; commit `feat(terms): terms resolve gives a project's survey columns their official IDs, or the reason for none`. Open pull request B.
