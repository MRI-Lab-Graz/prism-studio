# Local metrics: the project overlay and the "New metric" tab (phase 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A user can add a metric (layer 3) to their project, see it validate right away, and later share it: a project overlay `code/specification/terms/<modality>/` read by the validator, `prism_tools.py spec local list|add-term|remove` and `spec propose`, notices, and a "New metric" tab on a new Studio page.

**Architecture:** `src/spec_overlay.py` holds the overlay (read, write, remove, merge with the official registry, list, find unknown metrics, build a proposal from a local term). `load_specification(project_root=...)` merges the overlay into the specification that phase 0 made current per run. The CLI (`app/src/cli/commands/spec.py`) and the Flask routes (`specification_contribute` blueprint) are thin adapters over those functions. Layer 3 and `biosample` only; layers 1-2 and proposal format v2 are later phases.

**Tech Stack:** Python stdlib, Flask + Jinja + vanilla JS (like the other pages), pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-specification-contributions-design.md` (phase 1). Builds on phase 0 (`src/specification.py`, merged f3ec39d3).

## Global Constraints

- **Overlay layout** (design): `<project>/code/specification/terms/<modality>/<local-id>.json`; a local term file is exactly a *proposal term* (the fields `prism-specification`'s `term_proposal.py` allows; no `Status`), so `spec propose` copies it unchanged. A local term without `Status` is "local".
- **Official wins:** a local term whose file stem or `TermID` the official registry has is ignored (INFO "now official; remove the local copy"). The overlay only adds. Local terms never leak into another project's run (phase 0 isolation).
- **One implementation:** shape rules for local term files come from the vendored `scripts/specification/check_terms.py` (`type_problems`) and `term_proposal.py` (`check_proposal`), reached through `src.term_proposal`'s script-directory lookup (renamed public `specification_scripts_dir()`); the validator wheel build must copy those two scripts so the validator image behaves the same (`scripts/build_validator_wheel.py`).
- **IDs and paths:** only `prism:<slug>[.<specimen>]` IDs; the local part must `re.fullmatch` `^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)?$` before it becomes a file name (a trailing newline once slipped past `$`); no path comes from user input otherwise.
- **Hostile project data:** a shared project may carry bad overlay files. They are data: skipped when not a JSON object, ignored with a notice when the vendored `type_problems` or the ID rule fails; they never crash a validation.
- **GUI/CLI parity:** every page action is a `spec` command's backend function. The page never builds a proposal itself and sends nothing (it links to the prefilled form).
- **Gate:** `/api/spec/` joins the project-ready guard's exempt prefixes (configuration, like the template editor and survey customizer); the `spec` CLI commands are not gated.
- **Strict mode:** the design said strict mode turns local-item notices into warnings, but `strictMode` is not wired anywhere in the validator today; leave it (ledger ruling), do not wire it here.
- **v1 proposals carry at most 2 terms:** `spec propose --term` takes a parent with its local children (or one child) and errors with "propose in two steps" above 2; phase 2 lifts it.
- TDD (failing test first, watch it fail); full suite `python3 -m pytest tests -q -p no:cacheprovider --ignore=tests/e2e` stays green after every task (baseline 6010 passed on main f3ec39d3); dual-tree check `find src app/src -name spec_overlay.py` first; commits end with the attribution line; `/ponytail:ponytail-audit` before the merge.

## Review Focus

- **A shared project with a hostile overlay** (not-JSON, a list, wrong value types, an ID with a trailing newline or `../`, a term claiming an official alias): validation neither crashes nor lets it override official terms. Pinned in Tasks 1-2.
- **Isolation:** project A's local term is unknown in project B validated next in the same process, and in a worker thread. Pinned in Task 2.
- **The validator image:** `src/spec_overlay.py` is in the manifest, needs no pandas, and the wheel carries the two vendored scripts. Pinned in Task 2.
- **Add-time collisions:** adding a term whose ID, alias or label an official or an existing local term owns fails with the colliding term named. Pinned in Task 4.
- **Remove:** removing a parent removes its local children; unknown IDs and traversal attempts are errors. Pinned in Tasks 1 and 4.
- **XSS in the page:** column names, messages and paths from the project are shown with `textContent`, never `innerHTML`. Pinned in Task 6.

---

### Task 1: The overlay on disk

**Files:** Create `src/spec_overlay.py`, `tests/test_spec_overlay.py`; Modify `src/term_proposal.py` (rename `_specification_scripts` to public `specification_scripts_dir`, update its one caller and `tests/test_term_proposal.py` if it names it).

**Interfaces:**
- Produces: `class OverlayError(ValueError)`; `overlay_root(project_root) -> Path` (`<project>/code/specification`); `load_local_terms(project_root, modality="biosample") -> tuple[dict[str, dict], list[str]]` (file stem → term for each JSON object whose `TermID` local part equals the stem, matches the ID rule and passes the vendored `type_problems`; second item = one message per skipped file); `write_local_terms(project_root, modality, terms: list[dict]) -> list[Path]` (ID rule re-checked, `OverlayError` otherwise; JSON indent 2 + newline); `remove_local_terms(project_root, modality, term_id) -> list[Path]` (the file, plus the files whose `Parent` is `term_id`; unknown ID → `OverlayError`).

- [ ] **Step 1: Write failing tests** (tmp project dirs): `test_load_local_terms_reads_valid_files`, `test_load_skips_and_reports_bad_files` (not JSON, a JSON list, `Aliases: 5`, stem ≠ ID local part, `TermID` with trailing newline), `test_missing_overlay_is_empty`, `test_write_creates_one_file_per_term_without_status`, `test_write_refuses_a_bad_local_part` (`prism:../x`, `prism:a\n`, `prism:A`), `test_remove_parent_removes_children`, `test_remove_unknown_id_is_an_error`, `test_remove_cannot_leave_the_overlay_folder`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_spec_overlay.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement** it; the vendored script is loaded with `importlib.util.spec_from_file_location` from `specification_scripts_dir()`.
- [ ] **Step 4: Run** that file and `tests/test_term_proposal.py tests/test_cli_terms.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): the project overlay for local terms`.

### Task 2: The specification includes the overlay

**Files:** Modify `src/spec_overlay.py` (add `merge_terms`), `src/specification.py`, `app/src/runner.py` (both wrappers), `scripts/validator_manifest.txt`, `scripts/build_validator_wheel.py`; Test: `tests/test_spec_overlay_runs.py`, `tests/test_validator_wheel.py` (one added assertion).

**Interfaces:**
- Consumes: Task 1.
- Produces: `merge_terms(official: dict[str, dict], local: dict[str, dict]) -> tuple[dict, frozenset[str], tuple[str, ...]]` (merged with official first; the `TermID`s of the local terms in use; the stems of local files ignored because the official registry has the stem or the `TermID`); `Specification` gains `local_terms: frozenset[str] = frozenset()`, `ignored_local: tuple[str, ...] = ()`, `overlay_problems: tuple[str, ...] = ()`; `load_specification(rules=None, schemas=None, project_root=None)` merges `load_local_terms(project_root, m)` into `terms[m]` for each term modality when given; `validate_dataset` and `validate_subject_only` pass `project_root=os.path.abspath(root_dir)`.

- [ ] **Step 1: Write failing tests**: `test_a_local_term_validates_in_its_own_project` (project with `code/specification/terms/biosample/dhea-s*.json` and a biosample column `{"Term": "prism:dhea-s"}`: a TSV value `-1` gives the inherited `less than MinValue` error), `test_the_next_project_does_not_see_it` (same sidecar in project B without overlay: no `MinValue` error; run A then B in one process and A in a worker thread), `test_official_wins_on_collision` (a local file with an official stem is ignored and listed in `ignored_local`), `test_hostile_overlay_never_crashes_a_run` (the bad files of Task 1 in a project: `validate_dataset` returns issues, no exception), `test_the_wheel_carries_the_two_vendored_scripts` (the staged wheel tree contains `scripts/specification/check_terms.py` and `term_proposal.py`), plus the existing `tests/test_validator_manifest_closure.py`, `tests/test_validator_runs_without_pandas.py`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement**; add `src/spec_overlay.py` to the manifest; extend the wheel staging to copy the two scripts.
- [ ] **Step 4: Run** the new files and the full suite. Expected: PASS, full suite green.
- [ ] **Step 5: Commit** `feat(spec): validation reads the project overlay`.

### Task 3: Shared classification and the notices

**Files:** Modify `src/term_registry.py`, `app/src/validator.py` (`_check_biosample_terms`, `_check_biosample_sidecar`, `validate_sidecar`), `app/src/runner.py`; Test: `tests/test_validator_biosample_terms.py`, `tests/test_spec_overlay_runs.py`.

**Interfaces:**
- Produces: in `src/term_registry.py` `analyte_columns(sidecar_data: dict) -> list[tuple[str, dict]]` (the columns the term checks look at: dict values, not `Technical`/`Study`/`Metadata`, not `sample_id`/`collection_time`/`fasting`, `Units != "n/a"`); the validator uses it (no behaviour change); `_check_biosample_sidecar` receives `root_dir`.
- New INFOs (once per sidecar / once per run): a column resolving to a term in `spec.local_terms` → "`<col>`: uses the local term `<id>` (not official yet; it applies to this project only). Share it: `python prism_tools.py spec propose --project "<root>" --term <id>`"; for each `spec.ignored_local` stem, once at run start → "The local term `<id>` is now official: remove the local copy: `python prism_tools.py spec local remove --project "<root>" <id>`"; each `spec.overlay_problems` entry → a WARNING "ignored local specification file ...". The unknown-metric INFO now offers both: `spec local add-term --project "<root>" --data "<file>" --column "<col>"` (use it here now) and the existing `terms propose` (share it).

- [ ] **Step 1: Write failing tests**: a column using a local term gives the "uses the local term" INFO once per sidecar and not for official terms; an ignored local term gives the "now official" INFO once per run; a bad overlay file gives the WARNING; the unknown-metric INFO contains `spec local add-term`, `--project`, `terms propose` and the quoted arguments; `analyte_columns` skips the sample columns.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** and migrate `_check_biosample_terms` to `analyte_columns`.
- [ ] **Step 4: Run** the new tests and the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): notices for local, now-official and unknown metrics`.

### Task 4: Operations on the overlay

**Files:** Modify `src/spec_overlay.py`; Test: `tests/test_spec_overlay_ops.py`.

**Interfaces:**
- Consumes: Tasks 1-2; `src.term_proposal.build_proposal`, `check_with_specification`, `issue_url`, `load_inherited_sidecar`.
- Produces: `add_local_term(project_root, *, column, data_file=None, sidecar_file=None, label=None, modality="biosample") -> dict` (`{"proposal": ..., "written": [paths]}`; builds the proposal from the column against the merged registry, checks it with `check_with_specification` against the merged registry, writes the terms; `OverlayError` with the problems otherwise; exactly one of `data_file`/`sidecar_file`); `list_local_items(project_root) -> list[dict]` (`{"layer": 3, "modality", "id", "label", "path", "status": "local" | "now-official" | "invalid"}`); `find_unknown_metrics(project_root, modality="biosample") -> list[dict]` (`{"column", "data_file", "specimen", "units", "similar"}` for every analyte column of every `*_biosample.tsv` (not under `code/`, `derivatives/`, `sourcedata/`, `.git/`) whose inherited sidecar classifies it `unknown`, one entry per sidecar and column); `proposal_for_local_term(project_root, term_id, modality="biosample") -> dict` (`{"proposal", "issue_url", "problems"}`; the term plus its local children; `OverlayError("propose in two steps")` above 2 terms; checked against the OFFICIAL registry only).

- [ ] **Step 1: Write failing tests**: add from a data file with inherited sidecars, add from a sidecar file, add refuses an official metric (names `prism:cortisol`), refuses a colliding alias of an existing local term, refuses unknown/both sources; `list_local_items` shows `local`, `now-official` (stub an official term with the same stem), `invalid`; `find_unknown_metrics` finds `dhea_s` and not `cort` (alias) nor sample columns, once per sidecar for two TSVs sharing a root sidecar, and ignores `derivatives/`; `proposal_for_local_term` for a parent+child passes, for 3 terms raises, for a child-only local term whose parent is official passes.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_spec_overlay_ops.py -q -p no:cacheprovider`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** that file and the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): add, list, find and propose local metrics`.

### Task 5: The `spec` command line

**Files:** Create `app/src/cli/commands/spec.py`; Modify `app/src/cli/parser.py` (a `spec` parser: `local` → `list|add-term|remove`, and `propose`), `app/src/cli/dispatch.py`, `app/src/cli/entrypoint.py`; Test: `tests/test_cli_spec.py`, `tests/test_cli_dispatch_routing.py`.

**Interfaces:**
- Consumes: Task 4 (thin handlers; `--json` as in `terms`).
- Produces: `spec local list --project P [--json]`; `spec local add-term --project P (--data F | --sidecar F) --column C [--label L] [--json]`; `spec local remove --project P <term-id> [--json]`; `spec propose --project P --term ID [--out FILE] [--open] [--json]` (like `terms propose`: nothing is sent without `--open`; `--out` saves the bare proposal). Handlers `cmd_spec_local_list`, `cmd_spec_local_add_term`, `cmd_spec_local_remove`, `cmd_spec_propose`; dispatch keys `spec_local_list`, `spec_local_add_term`, `spec_local_remove`, `spec_propose`.

- [ ] **Step 1: Write failing tests** (subprocess, like `tests/test_cli_terms.py`): list on an empty project; add-term then list shows it and a following `prism.py` validation uses it; add-term for an official metric exits 1 naming the term; remove then list is empty; `spec propose --term` prints the proposal, opens nothing, `--out` writes a file the vendored `term_proposal.py check --file` accepts; routing cases.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** parser/dispatch/entrypoint as `terms` does.
- [ ] **Step 4: Run** them plus `tests/test_cli_command_import_boundaries.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): spec local list|add-term|remove and spec propose`.

### Task 6: The page

**Files:** Create `app/src/web/blueprints/specification_contribute.py` (blueprint `specification_contribute_bp`), `app/templates/specifications_contribute.html`, `app/static/js/modules/specification/contribute.js`; Modify `app/prism-studio.py` (register the blueprint in `modular_blueprints`; the `/specifications/contribute` route renders the new template; sidebar entry), `app/templates/specifications.html` (a "Contribute" link in the sidebar), `app/src/web/project_ready_guard.py` (`/api/spec/` exempt); Test: `tests/test_specification_contribute_routes.py`, `tests/test_project_ready_guard.py` (one case), `tests/e2e/test_every_page_loads.py` (add the page if it lists pages).

**Interfaces:**
- Consumes: Task 4 functions; the open project from `session["current_project_path"]` (400 `{"error": "Open a project first"}` without).
- Produces: `GET /api/spec/local` → `{"items": [...], "unknown_metrics": [...]}`; `POST /api/spec/local/add-term` (JSON `{"data_file", "column", "label"?}`) → `{"success", "proposal"?, "error"?}`; `POST /api/spec/local/remove` (`{"id"}`); `POST /api/spec/propose` (`{"id"}`) → `{"proposal", "issue_url", "problems"}`. The page has the three tabs of the design (only *New metric* active; the other two say "coming"), the project's local items with status and *Remove*, the unknown metrics with *Add to this project*, and *Propose…*: a modal showing the proposal, the "maintainers may rename it, your column name stays an alias" note, *Open the prefilled form on GitHub* (a link; absent with a paste hint when `issue_url` is null) and *Download proposal.json*.

- [ ] **Step 1: Write failing tests** with the Flask test client (reuse the app builder of `tests/test_api.py`/`tests/test_api_config_route.py`): each route without a project → 400; with a tmp project (set `session["current_project_path"]` through `client.session_transaction()`): list shows an added item, add-term writes the overlay, remove removes it, propose returns an `issue_url` starting with `https://github.com/MRI-Lab-Graz/prism-specification/issues/new`; `GET /specifications/contribute` returns 200 and the sidebar of every specification page links it; `is_gate_exempt("/api/spec/local", "GET")` is true; the template contains no `innerHTML` assignment of project data (a grep-style test on `contribute.js`).
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** blueprint, template, JS (vanilla, `fetch`, `textContent`), registration, guard exemption.
- [ ] **Step 4: Run** them and the full suite; run the e2e page test if Playwright is available locally (`python3 -m pytest tests/e2e/test_every_page_loads.py -q -p no:cacheprovider`, skip otherwise). Expected: PASS.
- [ ] **Step 5: Commit** `feat(spec): Contribute page with the New metric tab`.

### Task 7: Docs, checks, audit

**Files:** Modify `docs/CLI_REFERENCE.md` (`spec`), `CHANGELOG.md`, `CLAUDE.md` (a short note: local specification lives in `code/specification/`, validation reads it through `load_specification(project_root=...)`), `docs/studio/specifications.md` (the Contribute tab).

- [ ] **Step 1: Write** the docs.
- [ ] **Step 2: Run** the full suite, `python3 tests/verify_repo.py --check dual-tree-drift --no-fix` (delete its report), `python3 scripts/ci/check_specification_lock.py`. Expected: green.
- [ ] **Step 3: Run `/ponytail:ponytail-audit`** on the branch, apply what is worth it, re-run the suite, then ask before merging.
- [ ] **Step 4: Commit** `docs(spec): local metrics`.
