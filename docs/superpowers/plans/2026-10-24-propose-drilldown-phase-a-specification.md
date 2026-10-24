# Propose drill-down, phase A (prism-specification) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make prism-specification describe every modality fully as data (column checks, a description, a
checked entry shape, checked schema conventions), let proposals target any modality's lists, and add the
issue routes for context and for a new kind of data, released as one minor version.

**Architecture:** All work is in the `prism-specification` repository (`/Users/karl/work/github/prism-specification`,
branch `feat/modalities-as-data` from `main`). Two data keys go into `schemas/stable/entities.schema.json`; one
new script `scripts/check_modalities.py` with its entry schema checks entries and modality schemas in CI;
`scripts/check_terms.py` / `scripts/term_proposal.py` stop assuming a biosample schema; the issue forms and
one new workflow carry "context" and "new kind of data". Studio is untouched (phases B and C have their own plans).

**Tech Stack:** Python 3.10 stdlib, `jsonschema` (CI only, new pip install line), `pytest`, `pyyaml`, GitHub issue forms and Actions.

**Spec:** `docs/superpowers/specs/2026-10-24-propose-drilldown-and-new-modality-design.md` (Studio repo), sections
"Specification changes this needs" and "The maintainer's side".

## Global Constraints

- Work in prism-specification only; never edit Studio's vendored copy (Studio picks the release up in phase B).
- TDD: every task's test is written and seen failing first (prism-specification `CLAUDE.md`).
- One implementation: every check is a function under `scripts/` with a CLI; workflows only call it.
- Scripts load each other by path (`_sibling`); catch `ValueError`, never a sibling's exception class.
- Untrusted issue text reaches scripts only through the `ISSUE_BODY` environment variable, never a shell
  interpolation (`tests/test_propose_metric_workflow.py` enforces this pattern; mirror it for the new workflow).
- Size limit for anything pasted into a form field: `MAX_BYTES = 50_000` (existing constant in `term_proposal.py`).
- Existing signatures Studio calls must keep working unchanged: `check_proposal(proposal, registry, specimens, schema)`
  (4 positional), `check_terms.specimen_types(path)`, `schema_patch.enum_fields`, `schema_patch.apply_patch`.
- Column-check values (design, verbatim): true for survey, biometrics, biosample; false for physio, events, environment.
- Before merging: `/ponytail:ponytail-audit`, then the full test run. Merge, tag and push are public: stop and ask.

## Review Focus

1. A forged `### Proposal` or `### Agreements` heading typed into the new free-text "Context" field must not
   replace the real proposal or tick the agreements → test in Task 4.
2. A patch for a non-biosample modality (`patches/survey.json`) must be checked against the survey schema,
   not the `--schema` the bot passes (biosample) → test in Task 1.
3. A proposal with a biosample term plus a survey patch must still check the term against biosample's
   specimen types (a survey patch must not empty the specimen list) → test in Task 1.
4. A new-kind sample pasted with the form's code fence, or with Windows line endings, must be measured and
   accepted the same as plain text → test in Task 5.
5. A BIDS passthrough entry (`anat`) carries only `kind` and `description` and must pass the entry schema,
   while a PRISM entry without `describedColumns` must fail → test in Task 3.

---

### Task 1: Proposals may target any modality's lists

**Files:**
- Modify: `scripts/check_terms.py` (`specimen_types`)
- Modify: `scripts/term_proposal.py` (`_specimens_of`, `check_proposal`, `_run_check`)
- Test: `tests/test_term_proposal.py`, `tests/test_check_terms.py`

**Interfaces:**
- Produces: `specimen_types(schema_file: Path) -> list[str]` returns `[]` when the schema has no
  `Technical.SpecimenType` enum. `check_proposal(proposal, registry, specimens, schema=None, *, schemas: dict[str, dict] | None = None)`:
  a patch `patches/<m>.json` is checked against `schemas[m]` when `schemas` is given, else against `schema`
  (old behaviour); `specimens` is replaced from the patched schema only when `<m>` is in `MODALITIES`
  (the term modalities, today `("biosample",)`). `_run_check` builds `schemas` from
  `args.repo / "schemas/stable/<m>.schema.json"` for every patch in the proposal; a missing file is the problem
  `patches/<m>.json: no modality <m> in schemas/stable`.

- [ ] **Step 1: Write the failing tests**

```python
def test_specimen_types_is_empty_for_a_schema_without_specimens():
    assert check_terms.specimen_types(REPO / "schemas/stable/survey.schema.json") == []

def test_a_survey_patch_is_checked_against_the_survey_schema(tmp_path):
    proposal = {"format": "prism-proposal/2", "files": {"patches/survey.json": {"operations": [
        {"op": "add_enum_values", "path": "Study.LicenseID", "values": ["CC-BY-NC-4.0-local"]}]}}}
    # bot invocation: --schema is biosample, as in .github/workflows/propose-metric.yml
    code = run_check(proposal, tmp_path)   # existing helper that writes the file and calls main([... "check", ...])
    assert code == 0, (tmp_path / "out/log").read_text()
    assert (tmp_path / "out/files/schemas/stable/survey.schema.json").is_file()

def test_a_survey_patch_keeps_the_biosample_specimens_for_terms(tmp_path):
    # one biosample child term on saliva plus a survey patch: the term still checks against biosample specimens
    ...  # proposal with terms/biosample/<new>.json (+ parent) and patches/survey.json; expect exit 0
```

Use the existing `patches` value shape and run-helper in `tests/test_term_proposal.py` (read it first; reuse, do
not add a second helper). Pick an enum path that `schema_patch.enum_fields(survey schema)` actually lists.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest -q tests/test_term_proposal.py tests/test_check_terms.py`
Expected: the three new tests FAIL (`KeyError: 'SpecimenType'` / patch checked against biosample).

- [ ] **Step 3: Implement** the interfaces above. `_specimens_of` and `specimen_types` use `.get()` chains
  returning `[]`. Leave the 4-positional call path untouched for Studio.

- [ ] **Step 4: Run the whole suite**

Run: `python -m pytest -q`
Expected: all pass (count printed; compare with the count before the task plus 3).

- [ ] **Step 5: Commit**

```bash
git add scripts/check_terms.py scripts/term_proposal.py tests/test_term_proposal.py tests/test_check_terms.py
git commit -m "fix: proposals may patch any modality's lists, checked against that modality's schema"
```

### Task 2: Entities entries say whether columns are described, and what the modality is

**Files:**
- Modify: `schemas/stable/entities.schema.json` (`version` → `"1.1.0"`, two keys on entries)
- Modify: `specs/entities.md` (section "Per-modality rules": document both keys)
- Test: `tests/test_entities_schema.py`

**Interfaces:**
- Produces: on every entry `"description": "<one line, plain language>"`; on every `"kind": "prism"` entry
  `"describedColumns": true|false`. Phase B reads `describedColumns`; phase C shows `description` in the
  step-1 pull-down.

- [ ] **Step 1: Write the failing tests**

```python
def test_described_columns_marks_the_modalities_whose_tsv_columns_the_sidecar_describes():
    found = {name: e.get("describedColumns") for name, e in ENTITIES["modalities"].items() if e["kind"] == "prism"}
    assert found == {"survey": True, "biometrics": True, "biosample": True,
                     "physio": False, "events": False, "environment": False}

def test_every_modality_has_a_one_line_description():
    for name, entry in ENTITIES["modalities"].items():
        text = entry.get("description", "")
        assert text.strip() and "\n" not in text and len(text) <= 120, name
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest -q tests/test_entities_schema.py`
Expected: both FAIL (keys missing).

- [ ] **Step 3: Add the keys.** Descriptions in the page's plain language, for example biosample
  "Lab results from biological samples (blood, saliva, urine, ...)", physio "Continuous physiological
  recordings (ECG, respiration, skin conductance, ...)", anat "Structural MRI (BIDS, passed through)".
  Take the PRISM ones from each schema's `title`/`description` where they read well. Document both keys in
  `specs/entities.md` "Per-modality rules" (what `describedColumns` turns on: column-value checks and the
  strict file-name check).

- [ ] **Step 4: Run the whole suite and the generator check**

Run: `python -m pytest -q && python scripts/generate_schema_reference.py --check`
Expected: all pass, generator reports in sync.

- [ ] **Step 5: Commit**

```bash
git add schemas/stable/entities.schema.json specs/entities.md tests/test_entities_schema.py
git commit -m "feat(spec): entities entries carry describedColumns and a description (entities 1.1.0)"
```

### Task 3: One check for entries and modality schemas

**Files:**
- Create: `scripts/entities_entry.schema.json` (draft-07 schema of one entry; under `scripts/` so the schema-page
  guard `tests/test_schema_docs_in_sync.py` does not demand a spec page for it)
- Create: `scripts/check_modalities.py`
- Modify: `.github/workflows/ci.yml` (pip line adds `jsonschema`; new step "Modalities" runs the script)
- Test: `tests/test_check_modalities.py`

**Interfaces:**
- Produces: `check(entities: dict, schema_dir: Path) -> list[str]` (problem lines, empty = fine) and
  `main(argv) -> int` with `--entities PATH --schemas DIR` (defaults: this repo's
  `schemas/stable/entities.schema.json` and `schemas/stable`). Exit 1 and one line per problem when any.
- Entry schema: `additionalProperties: false`; properties `kind` (enum `prism`, `bidsPassthrough`),
  `description`, `describedColumns`, `suffixes`, `extensions`, `folder`, `allowedEntities`,
  `requiredEntityValues`, `optionalEntityValues`, `example`; always required `kind`, `description`;
  `if kind == prism then required suffixes, extensions, describedColumns`.
- Modality-schema conventions, for every `kind: prism` entry with `suffixes` (events has `folder: false`
  but a schema: include it), ported from Studio `tests/verify_repo.py::check_modality_schema_conventions`:
  the file `<schema_dir>/<name>.schema.json` exists; top-level keys `$schema`, `$id`, `version`, `title`,
  `description`, `type`, `properties`, `required`; `type == "object"`; every `required` key is in
  `properties`; `$id` ends with `/v<version>`; `jsonschema.Draft7Validator.check_schema` passes.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_repository_passes():
    assert mod.main([]) == 0

def test_an_unknown_entry_key_is_reported(tmp_path):
    entities = _entities(); entities["modalities"]["biosample"]["colour"] = "red"
    assert any("biosample" in p and "colour" in p for p in mod.check(entities, SCHEMAS))

def test_a_prism_entry_needs_described_columns_but_a_bids_entry_does_not():
    entities = _entities(); del entities["modalities"]["biosample"]["describedColumns"]
    problems = mod.check(entities, SCHEMAS)
    assert any("biosample" in p and "describedColumns" in p for p in problems)
    assert not any(p.startswith("anat") for p in problems)

def test_a_prism_modality_without_a_schema_file_is_reported(tmp_path):
    entities = _entities()
    entities["modalities"]["skin"] = {"kind": "prism", "description": "x", "suffixes": ["skin"],
                                      "extensions": ["tsv"], "describedColumns": True}
    assert any(p.startswith("skin") and "schema" in p for p in mod.check(entities, SCHEMAS))

def test_a_schema_whose_id_does_not_match_its_version_is_reported(tmp_path):
    ...  # copy schemas/stable to tmp_path, set biosample "$id" to ".../v9.9.9", expect a biosample $id problem
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest -q tests/test_check_modalities.py`
Expected: FAIL (`scripts/check_modalities.py` missing).

- [ ] **Step 3: Implement** the script and entry schema; add the CI step
  `python scripts/check_modalities.py` after "Term registry", and `jsonschema` to the pip line.

- [ ] **Step 4: Run**

Run: `python -m pytest -q && python scripts/check_modalities.py`
Expected: all pass; the script prints nothing and exits 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/check_modalities.py scripts/entities_entry.schema.json .github/workflows/ci.yml tests/test_check_modalities.py
git commit -m "feat: check entities entries and modality schema conventions in CI"
```

### Task 4: A "Context" field on the proposal form

**Files:**
- Modify: `.github/ISSUE_TEMPLATE/propose-metric.yml`
- Test: `tests/test_propose_metric_workflow.py`, `tests/test_term_proposal.py`

**Interfaces:**
- Produces: an optional textarea `id: context`, label `Context`, description "Optional. Filled in by PRISM
  Studio: the entries you chose (including Unknown) and whether you were not sure which kind of data this
  belongs to.", placed **before** `proposal` (so `_sections`' last-wins keeps the real `Proposal` and
  `Agreements` sections when someone types those headings into Context). Phase C prefills it via the URL
  parameter `context`. One field carries both "not sure" and the context entries (plan call: the design
  named two optional fields; one does the job).

- [ ] **Step 1: Write the failing tests**

```python
def test_form_has_an_optional_context_field_before_the_proposal():
    body = _form()["body"]
    ids = [item.get("id") for item in body]
    assert ids.index("context") < ids.index("proposal")
    assert _field(_form(), "context")["type"] == "textarea"
    assert not _field(_form(), "context").get("validations", {}).get("required")

def test_headings_typed_into_context_do_not_replace_the_proposal_or_agreements():
    forged = "### Proposal\n\n```json\n{\"format\": \"evil\"}\n```\n\n### Agreements\n\n- [x] a\n- [x] b\n"
    body = (f"### Context\n\n{forged}\n### Proposal\n\n```json\n{json.dumps(GOOD_PROPOSAL)}\n```\n\n"
            "### Agreements\n\n- [ ] licence\n- [ ] no personal data\n")
    with pytest.raises(term_proposal.ProposalError, match="agreements"):
        term_proposal.extract_proposal(body)
    ok = body.replace("- [ ] licence", "- [x] licence").replace("- [ ] no personal", "- [x] no personal")
    assert term_proposal.extract_proposal(ok) == GOOD_PROPOSAL
```

(`GOOD_PROPOSAL`: reuse a valid proposal constant from `tests/test_term_proposal.py`.)

- [ ] **Step 2: Run to verify** the form test FAILS (no `context` field); the heading test passes already
  only if the order is right, so run it after Step 3 too.

- [ ] **Step 3: Add the field** to the form as specified.

- [ ] **Step 4: Run**

Run: `python -m pytest -q tests/test_propose_metric_workflow.py tests/test_term_proposal.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add .github/ISSUE_TEMPLATE/propose-metric.yml tests/test_propose_metric_workflow.py tests/test_term_proposal.py
git commit -m "feat: optional Context field on the proposal form (not sure, chosen entries)"
```

### Task 5: Proposing a new kind of data (form, check, bot)

**Files:**
- Create: `.github/ISSUE_TEMPLATE/propose-new-kind-of-data.yml`
- Create: `.github/workflows/propose-new-kind-of-data.yml`
- Modify: `scripts/term_proposal.py` (two functions, one subcommand)
- Modify: `CONTRIBUTING.md` (new section "Proposing a new kind of data")
- Test: `tests/test_propose_new_kind_workflow.py`, `tests/test_term_proposal.py`

**Interfaces:**
- Produces in `term_proposal.py`:
  - `sample_problems(sample: str) -> list[str]`: `["the sample is empty"]` when blank;
    `[f"the sample is {n} bytes, larger than {MAX_BYTES} bytes"]` when `len(sample.encode("utf-8")) > MAX_BYTES`
    after one surrounding code fence is removed and `\r\n` is normalised. Phase C calls it from Studio.
  - `check_new_kind(issue_body: str) -> list[str]`: both agreement boxes ticked (same `_CHECKBOX` rule and
    message style as `extract_proposal`), `Description` section non-empty, `sample_problems` of the
    `Sample file` section. `Closest kind of data` is optional and unchecked (the maintainer decides).
  - Subcommand `check-new-kind`: reads `ISSUE_BODY`, prints one problem per line (capped like `_run_check`:
    `MAX_PROBLEMS` lines of `MAX_LINE` chars), exit 1 when any, else exit 0 and prints nothing.
- Form: name "Propose a new kind of data", labels `["type: new-kind-of-data", "status: needs-triage"]`; fields
  in this order: `description` (textarea, required, label `Description`), `closest_kind` (input, optional,
  label `Closest kind of data`), `sample` (textarea, required, label `Sample file`, `render: text`),
  `agreements` (two required boxes: licence as in the metric form; "The sample is made up and contains no
  real participant data."). Intro text says: a maintainer adds the new kind of data; PRISM validates such files
  only once it is merged and in a PRISM release; paste the sample, no attachments.
- Workflow: `on: issues: types: [opened]`, top-level `permissions: {}`, one job gated on the
  `type: new-kind-of-data` label with `permissions: {contents: read, issues: write}`; checkout default branch;
  run `python3 scripts/term_proposal.py check-new-kind > problems.txt` with `ISSUE_BODY` in `env`; comment with
  `gh issue comment "$ISSUE_NUMBER" --body-file` either the problems (asking to edit and re-open) or
  "Thanks! A maintainer will review this. PRISM can validate this kind of data once it is merged and released."
  No PR, no artifact, no download.

- [ ] **Step 1: Write the failing tests**

```python
def test_sample_problems_measures_the_text_without_its_fence_and_crlf():
    body = "a\tb\r\n1\t2\r\n"
    assert term_proposal.sample_problems(f"```\n{body}```") == term_proposal.sample_problems(body) == []
    assert term_proposal.sample_problems("  ") == ["the sample is empty"]
    assert "larger than 50000 bytes" in term_proposal.sample_problems("x" * 50_001)[0]

def test_check_new_kind_needs_description_sample_and_both_agreements():
    good = ("### Description\n\nSkin temperature from a wrist sensor\n\n### Closest kind of data\n\n_No response_\n\n"
            "### Sample file\n\n```\ntime\ttemp\n0\t33.1\n```\n\n### Agreements\n\n- [x] licence\n- [x] made up\n")
    assert term_proposal.check_new_kind(good) == []
    assert term_proposal.check_new_kind(good.replace("- [x] made up", "- [ ] made up"))
    assert term_proposal.check_new_kind(good.replace("Skin temperature from a wrist sensor", ""))

def test_new_kind_form_fields_and_order():   # in tests/test_propose_new_kind_workflow.py
    ids = [i.get("id") for i in _form()["body"] if i.get("id")]
    assert ids == ["description", "closest_kind", "sample", "agreements"]

def test_new_kind_workflow_passes_issue_text_only_through_env():
    # same assertions as test_propose_metric_workflow.py: no ${{ github.event.issue.* }} inside any `run:`,
    # top-level permissions {}, job permissions exactly {contents: read, issues: write}, label gate
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest -q tests/test_term_proposal.py tests/test_propose_new_kind_workflow.py`
Expected: FAIL (functions, form and workflow missing).

- [ ] **Step 3: Implement** the functions, subcommand, form, workflow and the CONTRIBUTING section
  (what to give: description, made-up sample, optional closest kind; what happens: maintainer builds the
  schema, entities entry and page in a normal PR; no local validation until released).

- [ ] **Step 4: Run the whole suite and all CI commands**

Run: `python -m pytest -q && python scripts/generate_schema_reference.py --check && python scripts/check_terms.py --terms terms/biosample --schema schemas/stable/biosample.schema.json && python scripts/check_modalities.py`
Expected: all pass, every command exits 0.

- [ ] **Step 5: Commit**

```bash
git add .github scripts/term_proposal.py CONTRIBUTING.md tests/test_propose_new_kind_workflow.py tests/test_term_proposal.py
git commit -m "feat: propose a new kind of data (issue form, check-new-kind, bot comment)"
```

### Task 6: Audit, then stop for the release

- [ ] **Step 1:** Run `/ponytail:ponytail-audit` on the branch; apply what is worth it (or note why not); re-run
  `python -m pytest -q` and the CI commands of Task 5 Step 4.
- [ ] **Step 2: STOP and ask the user** before merging into `main`, tagging `v1.3.0` (a minor release:
  content changed), and pushing; all three are public. After the push: one live check of the new-kind form
  (one good and one with an unticked box; close both test issues afterwards).
- [ ] **Step 3:** Hand over to the phase-B plan (Studio: `python scripts/sync_specification.py --tag v1.3.0`, derive
  the column-check set from `describedColumns`, drop `TABULAR_MODALITIES` and Studio's conventions check).
