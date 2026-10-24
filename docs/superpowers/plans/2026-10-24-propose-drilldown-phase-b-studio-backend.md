# Propose drill-down, phase B (Studio backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Studio carries prism-specification v1.3.0 and acts on it: column-value and strict file-name checks follow
`describedColumns` instead of a hand-written list, and a project's added values (patches) validate and can be shared
for every modality's lists, not only biosample's.

**Architecture:** Studio repo `/Users/karl/work/github/prism-studio`, branch `feat/modalities-as-data-studio` from `main`
in a worktree. The rule lives once in `src/entity_rules.py` (read from the vendored `entities.schema.json`) and is asked
through `current_specification()`; overlay and sharing code loop over the modalities that have a patch instead of
`("biosample",)`. The page (phase C) is not touched; these are the backend functions and CLI it will call.

**Tech Stack:** Python 3, pytest, the vendored scripts under `scripts/specification/` (loaded by path).

**Spec:** `docs/superpowers/specs/2026-10-24-propose-drilldown-and-new-modality-design.md` (sections "What can be used
before the merge", "Specification changes this needs", phase B). Phase A's plan
(`docs/superpowers/plans/2026-10-24-propose-drilldown-phase-a-specification.md`) produced the release this plan vendors.

## Global Constraints

- **Gate:** prism-specification `v1.3.0` must be tagged and pushed before Task 1. If `git ls-remote --tags
  https://github.com/MRI-Lab-Graz/prism-specification v1.3.0` prints nothing, STOP and ask the user (phase A's merge,
  tag and push are theirs to approve).
- Never edit vendored files (`app/schemas/stable|archive|v0.1|v0.2` except the Studio-owned ones, `official/library/terms/`,
  `docs/specs/` except `project.md`, `scripts/specification/`); they change only through `scripts/sync_specification.py`.
- Validation-path code asks `current_specification()`; never a module constant listing modalities
  (`tests/test_specification_boundaries.py`). A missing `describedColumns` means `False`.
- Dual-tree rule (CLAUDE.md): before editing any non-route file under `app/src/`, run
  `python3 -c "import src.<module> as m; print(m.__file__)"` and edit the file that answers; never duplicate an edit.
- Project overlay files are untrusted: a bad file is skipped and reported, never a crash; a file name becomes a modality
  only through `re.fullmatch(r"[a-z][a-z0-9]*", stem)` **and** membership in the run's schemas.
- One implementation: CLI commands and Flask routes call the same backend functions; no logic in `app/src/cli/commands/`.
- Validator image has no pandas: nothing on the validation path may import it.
- TDD for every task; `ponytail:ponytail-audit` before the merge; merging and pushing need the user's go.
- Enum values in patches are lowercase slugs (`[a-z][a-z0-9-]{0,62}`): use e.g. `cc-by-nc-local`, never mixed case.

## Review Focus

1. A patch file in `code/specification/patches/` whose stem is not a modality of the run (`Survey.json`, `unknown.json`,
   `x.y.json`) is skipped with a reported problem, never read as a modality and never a crash → test in Task 4.
2. Project A has a survey patch, project B none, both validated in one process: B must not see A's added value → test in Task 4.
3. A test fixture that writes its own `entities.schema.json` without `describedColumns` silently loses column checks for
   survey; the official copy must keep exactly survey, biometrics, biosample → test in Task 2, fixture sweep in Task 3.
4. A shared proposal with a biosample term **and** a survey patch is checked whole (term against biosample specimens, patch
   against the survey schema), without "the schema the patch targets is needed" → test in Task 5.
5. A survey patch that does not fit a version-pinned survey schema is reported as a problem for that run, not a crash → test in Task 4.

---

### Task 1: Vendor prism-specification v1.3.0

**Files:**
- Modify (by the sync script only): `app/schemas/...`, `scripts/specification/...`, `docs/specs/...`, `official/library/terms/...`, `specification.lock.json`
- Modify: `CHANGELOG.md` (Unreleased → Changed: "Studio carries prism-specification v1.3.0")

**Interfaces:**
- Produces: vendored `app/schemas/stable/entities.schema.json` 1.1.0 with `description` / `describedColumns`;
  `scripts/specification/check_modalities.py` and `scripts/specification/entities_entry.schema.json`;
  vendored `term_proposal.check_proposal(..., *, schemas=...)` and `sample_problems`.

- [ ] **Step 1: Check the gate** (Global Constraints). Expected: a line with `refs/tags/v1.3.0`.
- [ ] **Step 2: Sync**

Run: `python scripts/sync_specification.py --tag v1.3.0`
Expected: the lock names `v1.3.0`; `git diff --stat` touches only vendored paths and the lock.

- [ ] **Step 3: Verify**

Run: `python scripts/ci/check_specification_lock.py && python -m pytest -q tests/test_check_specification_lock.py tests/test_sync_specification.py tests/test_entity_rules.py tests/test_term_proposal.py tests/test_spec_overlay_*.py tests/test_specification_contribute_routes.py`
Expected: lock check OK; all pass (the new keys are ignored until Task 2).

- [ ] **Step 4: Commit**

```bash
git add -A app/schemas scripts/specification docs/specs official/library/terms specification.lock.json CHANGELOG.md
git commit -m "chore: sync prism-specification v1.3.0 (modalities described as data, proposals for every modality)"
```

### Task 2: Entity rules read `describedColumns` and `description`

**Files:**
- Modify: `src/entity_rules.py` (`ModalityRule`, `EntityRules`)
- Modify: `src/specification.py` (`Specification`)
- Test: `tests/test_entity_rules.py`, `tests/test_specification.py` (or the file that already tests `Specification`; reuse it)

**Interfaces:**
- Produces: `ModalityRule.described_columns: bool = False`, `ModalityRule.description: str = ""` (read from
  `describedColumns` / `description`); `EntityRules.described_columns_modalities -> set[str]` (names with
  `kind == "prism"` and `described_columns`, aliases included because they share the target's rule);
  `Specification.described_columns -> set[str]` (= `self.rules.described_columns_modalities`).

- [ ] **Step 1: Write the failing tests**

```python
def test_official_rules_describe_columns_of_exactly_three_modalities():
    assert load_entity_rules().described_columns_modalities == {"survey", "biometrics", "biosample"}

def test_a_rule_without_the_key_does_not_describe_columns():
    rule = ModalityRule.from_json("x", {"kind": "prism", "suffixes": ["x"], "extensions": ["tsv"]})
    assert rule.described_columns is False and rule.description == ""

def test_the_specification_exposes_the_described_columns_set():
    assert official_specification().described_columns == {"survey", "biometrics", "biosample"}
```

- [ ] **Step 2: Run to verify they fail** — `python -m pytest -q tests/test_entity_rules.py` → FAIL (`AttributeError`).
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Run** — `python -m pytest -q tests/test_entity_rules.py tests/test_specification*.py` → PASS.
- [ ] **Step 5: Commit** — `feat: entity rules and the specification know which modalities describe their columns`

### Task 3: The validator follows `describedColumns`; the hand-written list goes

**Files:**
- Modify: `app/src/validator.py` (the two `TABULAR_MODALITIES` uses: `validate_data_content` and the strict pattern check
  "strict for survey/biometrics" with the biosample-entity check inside it)
- Modify: `app/src/constants.py` (delete `TABULAR_MODALITIES` and its comment) — dual-tree check first
- Modify: `tests/test_entity_rules.py` (drop `test_...TABULAR_MODALITIES...` around line 138), `tests/test_specification_boundaries.py`
  (add `"TABULAR_MODALITIES"` to `FROZEN` so it cannot come back)
- Modify: test fixtures that write their own `entities.schema.json` with survey/biometrics/biosample entries
  (`tests/test_api.py`, `tests/test_modality_versions.py`, `tests/test_modality_version_pins.py`,
  `tests/test_verify_repo_modality_docs.py`; check each): add `"describedColumns": true` where the test relies on
  column checks, nothing where it does not
- Test: `tests/test_validator_described_columns.py` (new)

**Interfaces:**
- Consumes: `Specification.described_columns` (Task 2).

- [ ] **Step 1: Write the failing tests** (`tests/test_validator_described_columns.py`). Build a stand-in specification with
  `load_specification(rules=<official rules plus a "bloodwork" rule>, schemas=<official schemas plus a minimal bloodwork
  schema>)`; the bloodwork entry is `{"kind": "prism", "description": "Blood draws", "suffixes": ["bloodchem"],
  "extensions": ["tsv", "json"], "describedColumns": <True|False>}`. A tmp dataset holds
  `sub-01/bloodwork/sub-01_bloodchem.tsv` (`fasting` = `maybe`) and its sidecar (`fasting.AllowedValues: ["yes", "no"]`).

```python
def test_a_modality_added_by_data_gets_its_column_values_checked(tmp_path):
    issues = _content_issues(tmp_path, described_columns=True)   # validate_data_content under use_specification(...)
    assert any("maybe" in msg for level, msg in issues if level == "ERROR")

def test_without_described_columns_the_values_are_not_checked(tmp_path):
    assert _content_issues(tmp_path, described_columns=False) == []

def test_the_strict_file_name_check_follows_described_columns(tmp_path):
    bad = "sub-01_bloodchemX.tsv"
    assert _filename_errors(tmp_path, bad, described_columns=True)
    assert not _filename_errors(tmp_path, bad, described_columns=False)
```

- [ ] **Step 2: Run to verify they fail** — `python -m pytest -q tests/test_validator_described_columns.py` → FAIL
  (bloodwork is not in the hand-written list).
- [ ] **Step 3: Implement**: both sites read `current_specification().described_columns`; delete the constant; update
  the comment `# Check modality pattern (strict for survey/biometrics)` to name `describedColumns`.
- [ ] **Step 4: Run the full suite** — `python -m pytest -q -x -n auto` (or without `-n` if xdist is missing). Expected:
  all pass. A fixture failing here relied on the old list: add the key to that fixture (Files above), never re-add a list.
- [ ] **Step 5: Commit** — `feat(validator): column-value and strict file-name checks follow describedColumns, not a hand-written list`

### Task 4: A project's added values work for every modality

**Files:**
- Modify: `src/spec_overlay.py` (new `local_patch_modalities`; `_project_specimens` without the biosample-only `KeyError`)
- Modify: `src/specification.py` (`load_specification`: patches for every modality from `local_patch_modalities`, terms
  still only for `_TERM_MODALITIES`)
- Modify: `app/src/cli/parser.py` (`spec local add-values` / `remove-values`: `--modality` without `choices=["biosample"]`;
  the other `spec local` subcommands keep it)
- Test: `tests/test_spec_overlay_patches.py` (or the existing `tests/test_spec_overlay_*.py` that covers patches; reuse it),
  `tests/test_cli_dispatch_routing.py`

**Interfaces:**
- Produces: `local_patch_modalities(project_root, schemas: dict) -> tuple[list[str], list[str]]` = (modalities with a
  patch file, problems for skipped files). A stem counts only if `re.fullmatch(r"[a-z][a-z0-9]*", stem)` and
  `stem in schemas`; otherwise the problem `patches/<file name>: not a kind of data of this run`. Uses the same
  symlink-safe folder lookup the overlay already uses for patches (`_real_overlay_folder`).
- `add_local_values(project_root, field, values, modality=...)` already takes `modality`; an unknown modality or a field
  that `Specification.patchable_fields(modality)` does not list raises `OverlayError` with a message naming it.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_survey_patch_validates_its_new_value(tmp_path):
    project = _project(tmp_path)   # existing helper; add a survey file whose sidecar has Study.LicenseID "cc-by-nc-local"
    add_local_values(project, "Study.LicenseID", ["cc-by-nc-local"], modality="survey")
    spec = load_specification(project_root=project)
    assert "cc-by-nc-local" in _enum(spec.schemas["survey"], "Study.LicenseID") and "survey" in spec.local_patches

def test_patch_files_that_are_not_a_kind_of_data_are_skipped_and_reported(tmp_path):
    for name in ("Survey.json", "unknown.json", "x.y.json"):
        _write(tmp_path / "code/specification/patches" / name, {"operations": []})
    spec = load_specification(project_root=tmp_path)
    assert {p.split(":")[0] for p in spec.overlay_problems} >= {"patches/Survey.json", "patches/unknown.json", "patches/x.y.json"}

def test_a_survey_patch_does_not_leak_into_the_next_project(tmp_path):
    a, b = _project(tmp_path / "a"), _project(tmp_path / "b")
    add_local_values(a, "Study.LicenseID", ["cc-by-nc-local"], modality="survey")
    load_specification(project_root=a)
    assert "cc-by-nc-local" not in _enum(load_specification(project_root=b).schemas["survey"], "Study.LicenseID")

def test_a_patch_that_does_not_fit_the_runs_schema_is_a_problem_not_a_crash(tmp_path):
    _write(tmp_path / "code/specification/patches/survey.json",
           {"operations": [{"op": "add_enum_values", "path": "Study.NoSuchField", "values": ["x"]}]})
    assert any(p.startswith("patches/survey.json") for p in load_specification(project_root=tmp_path).overlay_problems)

def test_cli_add_values_accepts_another_modality():   # tests/test_cli_dispatch_routing.py, existing style
    args = build_parser().parse_args(["spec", "local", "add-values", "--project", "P", "--modality", "survey",
                                      "--field", "Study.LicenseID", "--value", "cc-by-nc-local"])
    assert args.modality == "survey"
```

- [ ] **Step 2: Run to verify they fail** — the focused files → FAIL (only biosample patches are loaded; parser rejects `survey`).
- [ ] **Step 3: Implement** the interfaces; `load_specification` applies each modality's patch with the existing
  `apply_patch` / `except ValueError` path and records it in `local_patches`.
- [ ] **Step 4: Run** the focused files plus `tests/test_specification_boundaries.py` → PASS; then the full suite once.
- [ ] **Step 5: Commit** — `feat: a project's added values validate for every modality (patches beyond biosample)`

### Task 5: Sharing works for every modality's lists

**Files:**
- Modify: `src/term_proposal.py` (`check_with_specification`)
- Modify: `src/spec_contribute.py` (`spec_catalog`: drop the `Technical.SpecimenType` skip and its comment; every modality
  with `patchable_fields` is listed; `specimens` stays biosample's)
- Test: `tests/test_term_proposal.py`, `tests/test_spec_contribute*.py` (whichever tests `spec_catalog`/`proposal_for_values`),
  `tests/test_specification_contribute_routes.py`

**Interfaces:**
- Consumes: vendored `check_proposal(..., schema, *, schemas=...)` (Task 1).
- Produces: `check_with_specification(proposal, registry, specimens=None)` unchanged in signature; it passes
  `schemas={m: <stable schema of m> for every "patches/<m>.json" in the v2 document}`; the term modality and its
  specimens are read from the `terms/<m>/...` paths, not from the first file (`_modality_of` is no longer used for that).
  `spec_catalog()["modalities"]` lists survey, biometrics, physio, environment as well (events has no list).

- [ ] **Step 1: Write the failing tests**

```python
def test_a_survey_list_addition_is_shared_without_problems():
    result = proposal_for_values("survey", "Study.LicenseID", ["cc-by-nc-local"])
    assert result["problems"] == [] and result["issue_url"]

def test_a_mixed_proposal_is_checked_whole():
    doc = _v2({**_biosample_term_files("dhea-s", "saliva"),
               "patches/survey.json": {"operations": [{"op": "add_enum_values", "path": "Study.LicenseID", "values": ["cc-by-nc-local"]}]}})
    assert check_with_specification(doc, load_registry("biosample")) == []

def test_the_catalog_lists_every_modality_with_a_list():
    names = {m["name"] for m in spec_catalog()["modalities"]}
    assert {"biosample", "survey", "biometrics", "physio", "environment"} <= names and "events" not in names
```

- [ ] **Step 2: Run to verify they fail** → FAIL ("the schema the patch targets is needed…"; catalog only has biosample).
- [ ] **Step 3: Implement.** The Propose page already renders whatever `spec_catalog` returns; check
  `tests/e2e/test_specification_contribute_flows.py` still passes (run it if Playwright is installed, else say so).
- [ ] **Step 4: Run** the focused files and the routes test → PASS.
- [ ] **Step 5: Commit** — `feat: list additions for every modality can be shared (catalog and checks no longer biosample-only)`

### Task 6: One conventions check, from the specification; maintainer notes up to date

**Files:**
- Modify: `.github/workflows/ci.yml` (drop `modality-schema-conventions` from both `verify_repo.py --check` lists; add a step
  `python scripts/specification/check_modalities.py --entities app/schemas/stable/entities.schema.json --schemas app/schemas/stable`)
- Modify: `tests/verify_repo.py` (delete `check_modality_schema_conventions`, `COMMUNITY_MODALITY_SCHEMAS`, its `CHECKS` entry)
- Delete: `tests/test_verify_repo_modality_schema_conventions.py`; update `tests/test_modality_build.py` where it names the check
- Modify: `src/modality_contribution.py` (`registration_entry` emits `description` (the proposal's `description`) and
  `describedColumns` (`True` when `"tsv"` is in the extensions); `build_registration_md` says: add schema, entities entry
  and `specs/<name>.md` in **prism-specification**, run its `check_modalities.py` and tests, tag a release, then
  `python scripts/sync_specification.py --tag <tag>` in Studio, then Studio's docs card/toctree/row and the fixture run)
- Modify: `docs/MODALITY_WORKFLOW.md`, `docs/MODALITY_PROPOSALS.md` (same steps; no `COMMUNITY_MODALITY_SCHEMAS`, no Studio-side schema edit)
- Test: `tests/test_modality_build.py` (or the test file of `registration_entry` / `build_registration_md`)

**Interfaces:**
- Consumes: vendored `scripts/specification/check_modalities.py` (`main(argv)`, `--entities`, `--schemas`).

- [ ] **Step 1: Write the failing tests**

```python
def test_registration_entry_carries_description_and_described_columns():
    entry = registration_entry(_proposal(extensions=["tsv"], description="Venous blood samples"))
    assert entry["description"] == "Venous blood samples" and entry["describedColumns"] is True

def test_registration_steps_point_to_prism_specification():
    text = build_registration_md(_proposal())
    assert "prism-specification" in text and "sync_specification.py --tag" in text
    assert "app/schemas/stable/entities.schema.json" not in text and "COMMUNITY_MODALITY_SCHEMAS" not in text

def test_the_vendored_conventions_check_passes_on_studios_copy():
    assert _vendored("check_modalities").main(["--entities", str(STABLE / "entities.schema.json"), "--schemas", str(STABLE)]) == 0
```

- [ ] **Step 2: Run to verify they fail** → FAIL.
- [ ] **Step 3: Implement** the file changes above.
- [ ] **Step 4: Run** — `python -m pytest -q tests/test_modality_build.py tests/test_modality_proposal_fixtures.py` and
  `python tests/verify_repo.py --check modality-docs --no-fix` and the new CI command → all pass.
- [ ] **Step 5: Commit** — `chore: modality schema conventions are checked by the vendored specification script; registration notes point to prism-specification`

### Task 7: Changelog, audit, stop

- [ ] **Step 1:** `CHANGELOG.md` Unreleased: Added (added values for every modality validate locally and can be shared),
  Changed (column checks follow `describedColumns`; conventions check from the specification). Commit.
- [ ] **Step 2:** `/ponytail:ponytail-audit` on the branch; apply what is worth it; full suite once.
- [ ] **Step 3: STOP and ask the user** before merging into `main` and pushing. Phase C (page, new-kind command, retiring
  Studio's modality issue form) gets its own plan.
