# One specification per validation (phase 0) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Everything the validator knows about modalities, schemas and terms comes from one `Specification` that is current for one validation run, instead of constants frozen at import and hand-written lists, with no change in behaviour.

**Architecture:** New `src/specification.py` (entity rules, schemas, terms; a `ContextVar` for the current one). `runner.validate_dataset` builds it and makes it current for the run; every validation-path module reads `current_specification()`. Outside a validation the official specification is current, so converters and CLI tools behave as today.

**Tech Stack:** Python stdlib (`contextvars`, `contextlib`, `dataclasses`, `functools`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-specification-contributions-design.md`, section "One specification per validation (phase 0)".

## Global Constraints

- **No behaviour change.** The full suite (`python3 -m pytest tests -q -p no:cacheprovider --ignore=tests/e2e`, 5983 passed on `main` f543b694) must stay green after every task; no existing test is edited to make it pass.
- New module in top-level `src/` (no `app/src/` copy); import it as `src.specification`; run `find src app/src -name specification.py` first.
- The module constants `validator.PRISM_MODALITIES`, `BIDS_MODALITIES`, `MODALITY_PATTERNS`, `_ENTITY_RULES` and `project_manager.PRISM_MODALITIES` stay, documented as the *official* values for code without a project (six test files import them); validation code stops reading them.
- Import-time constants that only concern official modalities may stay frozen, each with a one-line comment saying why: `survey_core._SURVEY_SUFFIX`, `converters/biometrics._BIOMETRICS_SUFFIX`, `cli/parser._rules` (argparse choices are built before any project exists), `bids_entity_rewriter._ENTITY_ORDER` / `_REQUIRED_ENTITIES`.
- A hand-written modality list is replaced by a derived set when it means "all modalities of a kind"; when it is a deliberate subset it stays, with a comment saying what it is. Each such decision is a ledger ruling.
- The validator image has no pandas: `src/specification.py` imports nothing that needs it (it is in the validator's import closure, so add it to `scripts/validator_manifest.txt`).
- Hot loops fetch `current_specification()` once per method, not per row or file.

## Review Focus

- **A worker thread** (Studio runs each validation in `threading.Thread`) does not inherit the caller's context: the run must set the specification inside the thread (it does, because `validate_dataset` sets it). Pinned in Task 2.
- **An exception during a run** resets the current specification (no leak into the next run). Pinned in Task 1.
- **Project A then project B in one process** (A under a stand-in specification with an extra modality): B does not see it. Pinned in Task 2.
- **Formatting after the run** (CLI printing, `issues.py` fix hints) happens after the context is reset and sees the official specification; that is correct in phase 0 and noted for phase 4. Pinned as a comment in Task 4.
- **Schema versions:** project pins and `--modality-version` must produce the same schemas as before through the new loader. Pinned in Task 2.

---

### Task 1: `src/specification.py`

**Files:** Create `src/specification.py`, `tests/test_specification.py`; modify `scripts/validator_manifest.txt`.

**Interfaces:**
- Produces: `@dataclass(frozen=True) class Specification: rules: EntityRules; schemas: dict; terms: dict[str, dict[str, dict]]` (terms per modality, today only `"biosample"`); `load_specification(schema_dir: str | None = None, version: str | None = None, modality_versions: dict | None = None, rules: EntityRules | None = None) -> Specification` (schemas via `load_all_schemas` with exactly the runner's arguments, rules via `load_entity_rules(schema_dir)` unless given, terms via `load_registry("biosample")`); `official_specification() -> Specification` (cached, no arguments); `use_specification(spec) -> ContextManager[Specification]` (sets the `ContextVar`, resets in `finally`); `current_specification() -> Specification` (the current one, else `official_specification()`).

- [ ] **Step 1: Write failing tests**: `test_outside_a_run_the_official_specification_is_current`, `test_use_specification_sets_and_resets` (also after an exception raised inside the `with`), `test_nested_use_restores_the_outer_one`, `test_a_new_thread_starts_with_the_official_specification` (set a stand-in in the main thread, read in a `threading.Thread`), `test_load_specification_matches_the_runner_schemas` (same keys and contents as `runner`'s current `load_all_schemas` call for the default arguments), `test_stand_in_rules_from_a_temp_entities_schema` (copy `app/schemas/stable/entities.schema.json` to `tmp_path/stable/`, add a modality `skinconductance`, `load_entity_rules(str(tmp_path))` → `load_specification(rules=...)` has it in `rules.project_modalities`; reused by Task 2).
- [ ] **Step 2: Run** `python3 -m pytest tests/test_specification.py -q -p no:cacheprovider`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** as specified; add `src/specification.py` to `scripts/validator_manifest.txt`.
- [ ] **Step 4: Run** the same file plus `tests/test_validator_manifest_closure.py tests/test_validator_runs_without_pandas.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(specification): one specification object, current per validation`.

### Task 2: The run makes its specification current

**Files:** Modify `app/src/runner.py` (`validate_dataset`, the schema-loading helper around line 112), `app/src/validator.py` (`DatasetValidator.__init__`: terms from the current specification); Test: `tests/test_specification_runs.py`.

**Interfaces:**
- Consumes: Task 1.
- Produces: `validate_dataset(..., specification: Specification | None = None)` — when `None`, it builds one with `load_specification(schema_dir, schema_version, explicit modality versions)` (same arguments as today); the whole run happens inside `use_specification(spec)`. `DatasetValidator.__init__` takes `self._terms = current_specification().terms.get("biosample", {})`.

- [ ] **Step 1: Write failing tests**: `test_validate_dataset_runs_under_its_specification` (monkeypatch a probe into `runner` that records `current_specification()` during the run; it is the passed stand-in, and after the run the official one is current again), `test_project_a_then_b_in_one_process_do_not_leak` (A validated with the stand-in from Task 1 and a file under `sub-01/skinconductance/`, then B with the official specification: B's issue list is identical to `validate_dataset(B)` run in a fresh process via `subprocess` + `python -c`), `test_validation_in_a_worker_thread_uses_its_own_specification`, `test_schema_pins_still_select_the_same_schemas` (a project with `SchemaVersions` in `project.json` gives the same `schemas` as before).
- [ ] **Step 2: Run** `python3 -m pytest tests/test_specification_runs.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement** in `runner.py` and `DatasetValidator.__init__`.
- [ ] **Step 4: Run** the new file and the full suite. Expected: PASS, full suite green.
- [ ] **Step 5: Commit** `refactor(validation): validate_dataset runs under its own specification`.

### Task 3: `validator.py` and `runner.py` read the current specification

**Files:** Modify `app/src/validator.py` (reads at lines ~1313, 1339, 1346, 1350, 1384, 1519; the hand-written set at ~358), `app/src/runner.py` (lines ~220-223, 793, 828, 920, 958, 1020); Test: `tests/test_specification_boundaries.py`.

**Interfaces:**
- Consumes: `current_specification().rules` (`prism_modalities`, `bids_modalities`, `modalities`, `pattern_for`, `entity_order`).
- Produces: a boundary test: in `app/src/validator.py`, `app/src/runner.py`, `app/src/fixer.py`, `app/src/project_manager.py`, `app/src/bids_validator.py`, `app/src/bids_integration.py`, `app/src/issues.py`, `app/src/reporting.py`, the names `_ENTITY_RULES`, `PRISM_MODALITIES`, `BIDS_MODALITIES`, `MODALITY_PATTERNS` appear only in their definition lines and `load_entity_rules(` is not called (an allow-list names the import-time exceptions of Global Constraints).

- [ ] **Step 1: Write the boundary test** (AST or line scan, like `tests/test_cli_command_import_boundaries.py`); it lists today's offenders. Run it. Expected: FAIL naming validator.py and runner.py lines (and the files of Tasks 4-5).
- [ ] **Step 2: Migrate** `validator.py` and `runner.py`: each method fetches `rules = current_specification().rules` once and uses it. Decide `validator.py:358` (`{"physio", "survey", "biometrics"}` in a physio context): a deliberate subset (suffixes accepted next to physio) → keep with a comment (ruling).
- [ ] **Step 3: Run** the full suite. Expected: green; the boundary test still fails only for the files of Tasks 4-5.
- [ ] **Step 4: Commit** `refactor(validation): validator and runner read the current specification`.

### Task 4: The other validation-path modules

**Files:** Modify `app/src/fixer.py` (~389, 394), `app/src/project_manager.py` (~534, 3211, 7059, 9183), `app/src/bids_validator.py` (`prism_only_folders`), `app/src/bids_integration.py` (~105), `app/src/issues.py` (~385-387: `hinted_modalities`), `app/src/reporting.py` (~1188), `src/methods_project.py` (`_MODALITY_DIRS`), `src/bids_entity_rewriter.py` (~43, call time).

- [ ] **Step 1: Tests first where behaviour is visible**: `test_issues_fix_hints_cover_every_project_modality` (a filename error in a `biosample` folder gets the same kind of hint as `survey` today) — fails now because `hinted_modalities` misses biosample; for each other list, decide derive-or-keep first and add a test only where deriving changes nothing visible today (then the boundary test is the guard).
- [ ] **Step 2: Run** them. Expected: the issues-hint test FAILS; the others pass.
- [ ] **Step 3: Migrate** each file to `current_specification()`; each keep/derive decision becomes a ledger ruling; `issues.py` gets a comment that hints formatted after a run see the official specification (phase 4 revisits it).
- [ ] **Step 4: Run** the full suite and the boundary test. Expected: all green, boundary test green.
- [ ] **Step 5: Commit** `refactor(validation): fixer, project manager, BIDS and reporting read the current specification`.

### Task 5: Docs, changelog, checks

**Files:** Modify `CLAUDE.md` (in the `src/` vs `app/src/` section or a short new one: validation code reads `current_specification()`, never the module constants, never a hand-written modality list), `CHANGELOG.md` (Unreleased: Changed (internal) + the fix-hint line), `docs/PROJECT_OVERVIEW.md` only if it names the constants.

- [ ] **Step 1: Write** the notes.
- [ ] **Step 2: Run** the full suite, `python3 tests/verify_repo.py --check dual-tree-drift --no-fix` (delete the report file it writes), `python3 scripts/ci/check_specification_lock.py`. Expected: green.
- [ ] **Step 3: Run `/ponytail:ponytail-audit`** on the branch, apply what is worth it, re-run the suite, then ask before merging.
- [ ] **Step 4: Commit** `docs: validation reads one current specification`.
