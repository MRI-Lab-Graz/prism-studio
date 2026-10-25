# Propose drill-down, phase C (Studio page and commands) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Propose page becomes the agreed drill-down (kind of data → accepted example beside the user's proposal →
measurements, plus "a new kind of data"), every step backed by a `prism_tools.py spec ...` command, and Studio's own
modality issue form and bot are retired in favour of prism-specification's.

**Architecture:** Studio repo, branch `feat/propose-drilldown-page` from `main` in a worktree. Backend functions in
`src/spec_contribute.py` (catalog, example entries, context text, new-kind proposal) and `src/term_proposal.py` (issue
URLs); thin routes in `app/src/web/blueprints/specification_contribute.py`; the page is
`app/templates/specifications_contribute.html` + `app/static/js/modules/specification/contribute.js`.

**Tech Stack:** Python 3, Flask, vanilla JS (no new dependency), pytest, Playwright (`tests/e2e`).

**Spec:** `docs/superpowers/specs/2026-10-24-propose-drilldown-and-new-modality-design.md` ("What the user sees",
"What can be used before the merge", "The maintainer's side", phase C). Phases A and B are merged (prism-specification
v1.3.0 vendored: new-kind form `propose-new-kind-of-data.yml` with fields `description`, `closest_kind`, `sample`,
`agreements`; metric form `propose-metric.yml` with the optional `context` field).

## Global Constraints

- Plain language on the page: the words modality, patch, enum, schema, TermID do not appear in page text (they stay in
  code, CLI and docs). Page text from data is written with `textContent` only, never `innerHTML`.
- Every choice with a finite answer is a pull-down; each pull-down appears only after the one above has a choice and
  starts on a forced "Choose…" entry. Pull-downs are derived from the current specification, never hand-written lists.
- One implementation: every page action is a backend function and a CLI command with the same options; routes and JS
  carry no logic of their own (CLAUDE.md "One implementation", GUI/CLI parity).
- Untrusted input: request bodies, project overlay files and library file names are checked in the backend; a modality
  name is accepted only if it is one of `current_specification().prism_modalities` (for project writes) or of the
  current specification's modalities (for the catalog and `closest`); template names must `re.fullmatch(r"[a-z0-9][a-z0-9-]*", ...)`.
- Studio sends nothing itself: sharing is a prefilled GitHub issue URL (limit `URL_LIMIT = 6000` characters in
  `src/term_proposal.py`) or a downloaded file. A sample file never goes into a URL; the user pastes it into the form.
- Sample size limit: the vendored `scripts/specification/term_proposal.py` `MAX_BYTES` / `sample_problems`; do not copy the number.
- Never edit vendored files; dual-tree rule for any non-route file under `app/src/`; nothing on the validation path imports pandas.
- Run tests as `PRISM_SKIP_VENV_CHECK=1 <main checkout>/.venv/bin/python -m pytest -q -p no:cacheprovider ...` (no xdist).
  Pre-existing on main: 11 e2e errors in the recipe flows and one flaky Projects-page e2e test; not this plan's breakage.
- TDD for every task; `ponytail:ponytail-audit` before merging; merge and push need the user's go.

## Review Focus

1. A new-kind request with a sample larger than the limit, a non-string description, or `closest` that is not a kind of
   data is refused with a clear message (HTTP 400 / CLI exit 1), nothing written, nothing echoed as HTML → tests in Task 3.
2. Context (not sure + chosen entries) that makes the issue URL longer than 6,000 characters: no URL, and the dialog shows
   the context text to paste; the context is never dropped silently → tests in Task 2 (backend) and Task 6 (page).
3. A kind of data without a library example (physio, environment, events) still shows its entries with an empty
   example column, no crash → test in Task 1.
4. A template name like `../x` or `Survey-AAI` in the example request is refused, nothing outside `official/library/` is read → test in Task 1.
5. A survey addition made with the CLI shows up in the page's "Additions in this project" with its kind of data and can
   be removed from there → tests in Task 4 (route) and Task 5 (page).

---

### Task 1: Catalog and accepted example for the drill-down

**Files:**
- Modify: `src/spec_contribute.py` (`spec_catalog`; new `example_entries`)
- Modify: `src/spec_overlay.py` (`_checked_modality`: also require `modality in current_specification().prism_modalities`)
- Modify: `app/src/web/blueprints/specification_contribute.py` (new GET route `/api/spec/example?modality=&template=`)
- Modify: `app/src/cli/parser.py`, `app/src/cli/commands/spec.py` (new `spec example --modality M [--template T] [--json]`)
- Test: `tests/test_spec_contribute.py`, `tests/test_specification_contribute_routes.py`, `tests/test_cli_spec.py`

**Interfaces:**
- Produces: `spec_catalog()["modalities"]` lists **every** modality of the current specification, sorted by name, each
  `{"name", "label": <ModalityRule.description or name>, "kind": "prism" | "bids", "lists": [...as today; [] when none],
  "metrics": [... as today, each also "specimens": [<SpecimenType of its child terms>]] | None, "templates": [<library stems>]}`.
  Existing callers (`_kinds`, `proposal_for_values`, `proposal_for_new_metric`, `cmd_spec_catalog`) keep working.
- Produces: `example_entries(modality: str, template: str | None = None) -> dict` =
  `{"modality", "template": str | None, "templates": [str], "entries": [{"field": "Technical.SpecimenType", "label": "Specimen type",
  "example": str | None, "values": [str] | None}]}`. Entries are the schema's leaf properties at depth 2 under each
  top-level object section except `Metadata` (the same walk as the vendored `schema_patch.enum_fields`, max depth 2);
  `values` is the enum (without `""`) or None for free text; `example` is the value in the library template
  (`official/library/<modality>/<template>.json`, default: the first stem alphabetically, `index.json` excluded), as text,
  or None. Find how Studio already locates `official/library/` (it must work in the frozen build) and reuse it.
  Unknown modality or bad template name → `OverlayError`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_catalog_lists_every_kind_of_data_with_a_description():
    mods = {m["name"]: m for m in spec_catalog()["modalities"]}
    assert {"biosample", "survey", "physio", "events", "anat"} <= set(mods)
    assert mods["anat"]["kind"] == "bids" and mods["anat"]["lists"] == []
    assert mods["biosample"]["label"].startswith("Lab results")
    assert "biosample-inflammation" in mods["biosample"]["templates"]

def test_example_entries_fill_the_example_from_the_library_template():
    ex = example_entries("biosample")
    by = {e["field"]: e for e in ex["entries"]}
    assert ex["template"] == "biosample-inflammation"
    assert by["Technical.SpecimenType"]["example"] == "serum" and "saliva" in by["Technical.SpecimenType"]["values"]
    assert by["Technical.Laboratory"]["values"] is None

def test_a_kind_without_a_library_example_still_lists_its_entries():
    ex = example_entries("physio")
    assert ex["template"] is None and ex["entries"] and all(e["example"] is None for e in ex["entries"])

@pytest.mark.parametrize("bad", ["../x", "Survey-AAI", "a/b"])
def test_a_bad_template_name_is_refused(bad):
    with pytest.raises(OverlayError):
        example_entries("survey", bad)

def test_project_writes_accept_only_prism_kinds(tmp_path):
    with pytest.raises(OverlayError):
        add_local_values(_project(tmp_path), "Name", ["x"], modality="project")
```

  Plus one route test (`GET /api/spec/example?modality=biosample` → 200 with the entries; `modality=../x` → 400) and one
  CLI test (`spec example --modality biosample --json`).

- [ ] **Step 2: Run to verify they fail** → FAIL.
- [ ] **Step 3: Implement** the interfaces.
- [ ] **Step 4: Run** the three test files plus `tests/test_spec_overlay_patches.py` → PASS.
- [ ] **Step 5: Commit** — `feat(spec): catalog of every kind of data and its accepted example (spec example)`

### Task 2: "Not sure" and the chosen entries travel with the proposal

**Files:**
- Modify: `src/term_proposal.py` (`issue_url(proposal, limit=URL_LIMIT, context: str | None = None)`)
- Modify: `src/spec_contribute.py` (new `proposal_context`; `proposal_for_values` / `proposal_for_new_metric` take `context`)
- Modify: routes `propose-values`, `propose-metric`; CLI `spec propose-values`, `spec propose-metric`
- Test: `tests/test_term_proposal.py`, `tests/test_spec_contribute.py`, `tests/test_specification_contribute_routes.py`, `tests/test_cli_spec.py`

**Interfaces:**
- Produces: `proposal_context(entries: dict[str, str] | None = None, not_sure: bool = False, closest: str | None = None) -> str | None`
  — plain text, one line per item: `Not sure which kind of data this belongs to (closest: <closest>)` when `not_sure`, then
  `<field>: <value>` per entry in the given order (`Unknown` kept as is); None when there is nothing. At most 100 entries,
  each value at most 200 characters, all strings, else `OverlayError`.
- `issue_url(..., context=...)` adds the query parameter `context` (the metric form's optional field) when given; the 6,000
  limit applies to the whole URL as today (None when longer).
- Result dicts of `proposal_for_values` / `proposal_for_new_metric` gain `"context": str | None`.
- CLI: both commands gain `--not-sure` and `--entry FIELD=VALUE` (repeatable); routes accept `not_sure` (bool) and
  `entries` (object of strings) in the JSON body.

- [ ] **Step 1: Write the failing tests**

```python
def test_context_lists_not_sure_and_the_entries_in_order():
    text = proposal_context({"Technical.SpecimenType": "sweat", "Technical.Laboratory": "Unknown"}, not_sure=True, closest="biosample")
    assert text.splitlines() == ["Not sure which kind of data this belongs to (closest: biosample)",
                                 "Technical.SpecimenType: sweat", "Technical.Laboratory: Unknown"]
    assert proposal_context() is None

def test_the_issue_url_carries_the_context():
    url = proposal_for_values("survey", "Study.LicenseID", ["cc-by-nc-local"], context="Study.Category: Unknown")["issue_url"]
    assert "context=Study.Category%3A%20Unknown" in url

def test_a_context_too_long_for_the_url_gives_no_url_but_keeps_the_context():
    result = proposal_for_values("survey", "Study.LicenseID", ["cc-by-nc-local"], context="x" * 7000)
    assert result["issue_url"] is None and result["context"] == "x" * 7000
```

- [ ] **Step 2: Run to verify they fail** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the four files → PASS.
- [ ] **Step 5: Commit** — `feat(spec): proposals carry "not sure" and the chosen entries as context`

### Task 3: Proposing a new kind of data (backend, route, CLI)

**Files:**
- Modify: `src/term_proposal.py` (constant `ISSUE_NEW_KIND_TEMPLATE = "propose-new-kind-of-data.yml"`)
- Modify: `src/spec_contribute.py` (new `proposal_for_new_kind`)
- Modify: blueprint (POST `/api/spec/propose-new-kind`), parser + `app/src/cli/commands/spec.py` (`spec propose-new-kind`)
- Test: `tests/test_spec_contribute.py`, `tests/test_specification_contribute_routes.py`, `tests/test_cli_spec.py`

**Interfaces:**
- Produces: `proposal_for_new_kind(description: str, sample: str, closest: str | None = None) -> dict` =
  `{"issue_url": str | None, "text": str, "problems": [str]}`. `problems`: `"the description is empty"` when blank, plus the
  vendored `sample_problems(sample)`. `closest` must be a modality of the current specification (else `OverlayError`).
  `issue_url`: `https://github.com/MRI-Lab-Graz/prism-specification/issues/new?template=propose-new-kind-of-data.yml` with
  `title` = `[New kind of data]: ` + the first line of the description cut to 60 characters, `description`, and
  `closest_kind` when given — never the sample; None if over `URL_LIMIT` or when there are problems. `text` (the download):
  `Description:\n<description>\n\nClosest kind of data: <closest or "not given">\n\nSample file:\n<sample>\n`.
- CLI: `spec propose-new-kind --description TEXT --sample FILE [--closest NAME] [--out FILE] [--open] [--json]`; the sample
  file is read as UTF-8 text; a file over the vendored `MAX_BYTES` is refused before decoding (read at most MAX_BYTES+1 bytes).
  `--open` opens the URL only when there are no problems. Exit 1 on problems.
- Route: JSON body `{description, sample, closest}`, all strings (closest optional); a non-string or an oversize sample → 400 with the problem.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_new_kind_proposal_prefills_the_form_but_not_the_sample():
    result = proposal_for_new_kind("Skin temperature from a wrist sensor\nOne file per session.", "time\ttemp\n0\t33.1\n", "physio")
    assert result["problems"] == []
    url = result["issue_url"]
    assert "template=propose-new-kind-of-data.yml" in url and "closest_kind=physio" in url and "33.1" not in url
    assert "Sample file:\ntime\ttemp" in result["text"]

def test_an_empty_description_and_a_huge_sample_are_problems():
    result = proposal_for_new_kind("  ", "x" * 50_001)
    assert "the description is empty" in result["problems"] and any("larger than" in p for p in result["problems"])
    assert result["issue_url"] is None

def test_closest_must_be_a_kind_of_data():
    with pytest.raises(OverlayError):
        proposal_for_new_kind("x", "a\tb\n", "../x")
```

  Plus route tests (good request → 200 with `issue_url`; `sample` not a string → 400; oversize → 400) and a CLI test with
  a sample file and `--json`.

- [ ] **Step 2: Run to verify they fail** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the three files → PASS.
- [ ] **Step 5: Commit** — `feat(spec): propose a new kind of data from Studio (spec propose-new-kind)`

### Task 4: Project routes for every kind of data

**Files:**
- Modify: `src/spec_overlay.py` (new `list_all_local_items(project_root) -> list[dict]`)
- Modify: blueprint routes `/api/spec/local` (GET), `add-values`, `remove-values`, `propose` (patch) — take `modality`
  (body or query, default `biosample`), checked by the backend
- Test: `tests/test_spec_overlay_patches.py`, `tests/test_specification_contribute_routes.py`

**Interfaces:**
- Produces: `list_all_local_items(project_root)` = biosample's local terms plus the patch items of every modality from
  `local_patch_modalities`, each item carrying `"modality"`; the `/api/spec/local` route returns it (existing keys kept).
- `add-values` / `remove-values` / `propose` routes pass the request's `modality` to the existing backend functions
  (`add_local_values`, `remove_local_values`, `proposal_for_local_terms(..., modality=..., include_patch=True)`); a bad
  name gives 400 with the backend's message.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_local_list_shows_a_survey_addition(client, project):
    add_local_values(project, "Study.LicenseID", ["cc-by-nc-local"], modality="survey")
    items = client.get("/api/spec/local").get_json()["items"]
    assert any(i["modality"] == "survey" and "cc-by-nc-local" in str(i) for i in items)

def test_add_and_remove_values_honour_the_kind_of_data(client, project):
    body = {"modality": "survey", "field": "Study.LicenseID", "values": ["cc-by-nc-local"]}
    assert client.post("/api/spec/local/add-values", json=body).status_code == 200
    assert client.post("/api/spec/local/remove-values", json=body).status_code == 200
    assert client.post("/api/spec/local/add-values", json={**body, "modality": "../x"}).status_code == 400
```

  (Use the existing route-test fixtures for an open project; name them as the file already does.)

- [ ] **Step 2: Run to verify they fail** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** both files → PASS.
- [ ] **Step 5: Commit** — `feat(spec): the project routes of the Propose page work for every kind of data`

### Task 5: The page, steps 1 and 2 (kind of data, example beside the proposal)

**Files:**
- Modify: `app/templates/specifications_contribute.html`, `app/static/js/modules/specification/contribute.js`
- Modify: `docs/studio/specifications.md` (the page section)
- Test: `tests/e2e/test_specification_contribute_flows.py` (rewrite the flows of the old step-1 choice)

**Interfaces:**
- Consumes: `/api/spec/catalog`, `/api/spec/example` (Task 1), `/api/spec/propose-values` with `not_sure`/`entries` (Task 2),
  the project routes with `modality` (Task 4), the existing share dialog.

What the page does (from the design, binding):
1. Step 1: pull-down "What kind of data?" starting on "Choose the kind of data…", options = every catalog modality with its
   `label` (the BIDS ones already read "… (BIDS, passed through)"), last option "Nothing fits: a new kind of data". A "Not sure" tick
   next to it. Choosing a BIDS kind shows one sentence that PRISM passes it to BIDS unchanged, nothing else.
2. Step 2 (a PRISM kind with entries): two columns. Left: the accepted example (`example` per entry; a template pull-down
   when `templates` has more than one; "no example yet" when none). Right: per entry a pull-down (`values` + "Missing: add a
   value…" + "Unknown") or, for free text, a text box with an "Unknown" choice. "Missing: add a value…" reveals a text box.
3. Only "Missing" entries become proposed additions (one `propose-values` call per list, through the existing dialog);
   all other filled or "Unknown" entries and the Not-sure tick go as `entries`/`not_sure` context.
4. "Use in my open project" (with a project open) adds the "Missing" values via `add-values` with the chosen kind; the
   phase-B biosample-only note (`#spec-v-use-note`) goes. "Additions in this project" lists `list_all_local_items` with the kind.
5. When the dialog has no URL (too long), it shows the proposal and the context text to paste.

- [ ] **Step 1: Write the failing e2e tests** (existing fixtures/server of the file; one test per behaviour):
  choosing Biosample shows the example column with "serum" and a pull-down for Specimen type; choosing "Missing: add a
  value…" for Specimen type and typing `sweat`, then Share, opens the dialog whose link contains `sweat` and
  `context=`; choosing "Structural MRI (BIDS, passed through)" shows the pass-through sentence and no step 2; with a project open, Use adds a survey
  value and it appears under "Additions in this project" with its kind and can be removed; no page text contains the words
  modality, patch, enum, schema (check `document.body.innerText`, excluding command literals in `code` elements).
- [ ] **Step 2: Run to verify they fail** → FAIL.
- [ ] **Step 3: Implement** (textContent only; no logic beyond showing, hiding and collecting choices).
- [ ] **Step 4: Run** `tests/e2e/test_specification_contribute_flows.py` and `tests/test_specification_contribute_routes.py` → PASS.
- [ ] **Step 5: Commit** — `feat(gui): Propose page drill-down, kind of data and accepted example beside the proposal`

### Task 6: The page, step 3 and a new kind of data

**Files:**
- Modify: template, `contribute.js`, `docs/studio/specifications.md`
- Test: `tests/e2e/test_specification_contribute_flows.py`

What the page does (binding):
1. Step 3, only for kinds with `metrics`: a pull-down of the official measurements (label, ID, unit), for biosample
   only those whose `specimens` contain the specimen chosen in step 2 when one was chosen, ending with
   "Missing: add a measurement…", which opens today's measurement form (prefilled sample type) — its share sends the context too.
2. "Nothing fits: a new kind of data": a form with a description (textarea, required), a sample (paste textarea or pick a
   text file, read in the browser as text), the closest kind (pull-down of the catalog, optional, prefilled with the step-1
   choice if the user had made one), and before Share the sentence from the design: *"A new kind of data is added by the
   maintainer. Until it is merged and in a PRISM release, PRISM cannot validate these files. Plan for this before your study
   starts."* Share calls `/api/spec/propose-new-kind`; the dialog shows problems, opens the prefilled form, tells the user to
   paste the sample into the "Sample file" field, and offers "Download" of `text`.

- [ ] **Step 1: Write the failing e2e tests**: biosample with Saliva chosen lists cortisol and alpha-amylase but not CRP;
  "Missing: add a measurement…" opens the form with sample type saliva; the new-kind form shows the "cannot validate" sentence,
  refuses an empty description with the backend's message, and for a good one opens a link with
  `propose-new-kind-of-data.yml` and the paste instruction.
- [ ] **Step 2: Run to verify they fail** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the e2e file → PASS.
- [ ] **Step 5: Commit** — `feat(gui): Propose page measurements step and a new kind of data`

### Task 7: Retire Studio's own modality issue form and bot; docs

**Files:**
- Delete: `.github/ISSUE_TEMPLATE/propose-modality.yml`, `.github/workflows/propose-modality.yml`,
  `scripts/ci/modality_issue_to_files.py`, `tests/test_modality_issue_to_files.py`, `tests/test_propose_modality_issue_form.py`,
  `tests/test_propose_modality_workflow.py`
- Modify: `scripts/ci/pr_scope.py` (drop `BOT_BRANCH_PREFIX` and what only served it; keep its other behaviour and tests)
- Modify: `docs/MODALITY_WORKFLOW.md`, `docs/MODALITY_PROPOSALS.md` (users propose on the Propose page or the
  "Propose a new kind of data" form in prism-specification; `modality propose` stays the maintainer's drafting tool),
  `docs/CLI_REFERENCE.md` (`spec example`, `spec propose-new-kind`, the new `--not-sure` / `--entry` options)
- Test: `tests/test_pr_scope*.py` (whatever covers pr_scope), plus a grep test or check

- [ ] **Step 1: Write the failing test**: a test asserting no file under `.github/` or `docs/` (excluding `docs/superpowers/`)
  links `prism-studio/issues/new?template=propose-modality.yml` and that `.github/ISSUE_TEMPLATE/propose-modality.yml` does not exist.
- [ ] **Step 2: Run to verify it fails** → FAIL.
- [ ] **Step 3: Delete and update** the files above; run `grep -rn "propose-modality\|modality_issue_to_files\|BOT_BRANCH_PREFIX" .github scripts src app tests docs --exclude-dir=superpowers` → no hits.
- [ ] **Step 4: Run** the pr_scope tests, the new test, `tests/test_modality_proposal_fixtures.py` → PASS.
- [ ] **Step 5: Commit** — `chore: retire Studio's propose-modality form and bot (prism-specification takes new kinds of data)`

### Task 8: Changelog, audit, stop

- [ ] **Step 1:** `CHANGELOG.md` Unreleased: the drill-down page, "not sure" and context, proposing a new kind of data,
  project additions for every kind on the page, the retired Studio form. Commit.
- [ ] **Step 2:** Full suite once (no `-n`); `/ponytail:ponytail-audit` on the branch; apply what is worth it.
- [ ] **Step 3: STOP and ask the user** before merging into `main` and pushing.
