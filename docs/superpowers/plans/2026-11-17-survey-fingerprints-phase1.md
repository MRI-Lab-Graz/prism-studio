# Survey Fingerprints, Phase 1 (local half) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A project can fingerprint its own (non-shareable) survey sidecar, and `terms resolve` gives that project's columns item IDs from those fingerprints. Nothing is shared or vendored.

**Architecture:** One new module `src/survey_fingerprints.py` (hashes of an item's wording per language and of its scale), a loader/writer next to the existing term overlay in `src/spec_overlay.py` (`code/specification/survey/<task>.json`), and `resolve_survey_sidecar` in `src/survey_terms.py` gains a project argument and a `source` per column. CLI only: `spec local add-survey`, `spec local remove-survey`, `terms resolve --project`.

**Tech Stack:** Python stdlib (`hashlib`, `json`, `unicodedata`), pytest, the existing argparse CLI under `app/src/cli/`.

**Spec:** `docs/superpowers/specs/2026-11-17-survey-fingerprints-design.md` (Phase 1 of its roadmap: local half; Phases 2 and 3 are separate plans).

## Global Constraints

- THE RULE: logic in `src/`, the CLI runs it. No Studio route is added in Phase 1: nothing in Studio calls `resolve_survey_sidecar` today (`grep` shows only `app/src/cli/commands/terms.py`), so there is no Studio side to keep in parity. The Contribute page option and its parity test belong to Phase 3.
- Do not edit vendored files (`official/library/**`, `app/schemas/**`, `scripts/specification/**`).
- Fingerprint file: `"Version": 1`, canonical JSON for hashing = `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, SHA-256 hex (64 chars, lowercase).
- Wording hash input: Unicode NFC of `_collapse(text)` (`src/survey_terms.py`), case and punctuation kept. Scale hash input: `{"Levels": sorted(str(k) for k in Levels) or None, "MinValue": ..., "MaxValue": ...}`; a float with an integer value counts as that integer.
- An item without `Description` is matched on scale alone. Item order, labels of levels, study metadata are never hashed.
- Language of a column: `Technical.Language` of the sidecar, default `en` (as `resolve` does today).
- Project files are untrusted: invalid file is skipped and reported, never a crash; file stem = task validated with `_LOCAL.fullmatch` (the `prism:<slug>` rule); writing goes through `_real_overlay_folder` (no symlinks); nothing is overwritten silently.
- The new JSON files are plain git (DataLad text policy); no `.gitattributes` code is touched.
- TDD: each task starts with a failing test. Subagents run on Sonnet 5.5, model set explicitly.
- Branch `feat/survey-fingerprints`; before merge run `ponytail:ponytail-audit`, `/code-review` and `/security-review` (reads project data).

## Review Focus

- A sidecar whose `Description` is a language dict with several languages: one hash per language, `--language` selects one.
- `Levels` keys `1`, `1.0`, `"01"`: `1` and `1.0` are the same code in the scale hash, `"01"` is different (session-style strings are never normalized).
- A symlinked `code/specification` (shared project) must make `add-survey` refuse, as for terms.
- A hostile local file (not an object, wrong Version, a hash that is not 64 hex chars, Task not equal to the file stem) is skipped with a message, `resolve` still runs.
- Two sidecars for the same task added in different languages merge; a second add of the *same* language is refused with a message naming the file (nothing overwritten).
- Known narrowing: a library-sourced task keeps today's lenient comparison (a missing min/max matches). Only fingerprint-sourced matches are exact.

## File Structure

- Create `src/survey_fingerprints.py`: hashing and `fingerprint_sidecar`. No I/O.
- Modify `src/spec_overlay.py`: `load_local_survey`, `write_local_survey`, `remove_local_survey` (survey folder helpers next to the terms ones).
- Modify `src/survey_terms.py`: `resolve_survey_sidecar` gets `project_root`, a `source` per column.
- Modify `app/src/cli/commands/spec.py`, `app/src/cli/commands/terms.py`, `app/src/cli/parser.py` (and `app/src/cli/dispatch.py` if it lists commands): the three CLI changes.
- Modify `docs/CLI_REFERENCE.md`.
- Tests: `tests/test_survey_fingerprints.py`, `tests/test_spec_overlay_survey.py`, additions to `tests/test_survey_terms.py`, `tests/test_cli_spec.py`, `tests/test_cli_terms.py`.

---

### Task 1: Fingerprint functions

**Files:**
- Create: `src/survey_fingerprints.py`
- Test: `tests/test_survey_fingerprints.py`

**Interfaces:**
- Produces:
  - `scale_hash(item: dict) -> str`
  - `wording_hashes(description, language: str) -> dict[str, str]` (language -> hash; plain string description is taken as `language`; non-text gives `{}`)
  - `fingerprint_sidecar(sidecar: dict, language: str | None = None) -> dict` returning `{"Version": 1, "Task": <slug of Study.TaskName>, "Items": {key: {"Wording": {lang: hash}, "Scales": [hash, ...]}}}`; items are the keys that are no `_NOT_ITEMS`, are dicts and have no `AliasOf`; `Scales` = the item's own scale hash plus one per `VariantScales` entry, de-duplicated, order kept; `language` restricts `Wording` to that language and raises `ValueError` when it is not carried by the sidecar (for a single-language string `Description`, the sidecar's `Technical.Language` default `en` must equal it).
  - `item_matches(entry: dict, column: dict, language: str) -> str`: the reason a column is not that fingerprinted item (`""` match, else `changed scale`, `changed wording`, `language not registered`, `alias`); wording is only compared when the column has a `Description`.

- [ ] **Step 1: Write the failing tests** in `tests/test_survey_fingerprints.py`: `test_scale_hash_ignores_level_labels_and_order` (two Levels with same keys, different labels/order: equal); `test_scale_hash_treats_1_and_1_0_alike_but_not_01` (`Levels` keys `1` vs `1.0` equal; `"01"` differs; MinValue `1.0` equals `1`); `test_wording_hash_collapses_whitespace_and_keeps_case`; `test_wording_hashes_one_per_language_of_a_dict`; `test_fingerprint_sidecar_includes_variant_scales`; `test_fingerprint_sidecar_skips_alias_and_non_items`; `test_fingerprint_sidecar_language_selects_one_or_raises`; `test_fingerprint_holds_no_item_text` (the serialized fingerprint contains none of the sidecar's description strings); `test_item_matches_reasons` (changed scale, changed wording, language not registered, alias, match).
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_survey_fingerprints.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `src/survey_fingerprints.py` with the signatures above. Reuse `_collapse`, `_texts`, `_slug`, `_valid` and `NOT_ITEMS` from `src/survey_terms.py` / `src/template_languages.py`; do not write a second normalizer.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(survey): fingerprints of an item's wording and scale`.

---

### Task 2: A project's local survey fingerprints (file I/O)

**Files:**
- Modify: `src/spec_overlay.py` (next to `load_local_terms`, same style)
- Test: `tests/test_spec_overlay_survey.py`

**Interfaces:**
- Consumes: `fingerprint_sidecar` from Task 1, `OverlayError`, `_real_overlay_folder`, `overlay_root`, `_scripts()[1]._LOCAL` (task slug rule).
- Produces:
  - `load_local_survey(project_root) -> tuple[dict[str, dict], list[str]]`: task slug -> file content for each valid `code/specification/survey/<task>.json`, plus one message per skipped file. Valid = JSON object, `Version == 1`, `Task == file stem`, `Items` a dict of `{"Wording": {lang: 64-hex}, "Scales": [64-hex, ...]}`.
  - `write_local_survey(project_root, fingerprint: dict, language: str | None) -> Path`: new task writes the file; an existing task merges only the language(s) not yet there (items must be the same keys or the new ones are added); the same language already present raises `OverlayError` naming the file; symlinked folder raises `OverlayError`.
  - `remove_local_survey(project_root, task: str) -> Path`: removes the file; unknown task or symlink raises `OverlayError`.

- [ ] **Step 1: Write the failing tests:** `test_write_then_load_round_trip`, `test_load_skips_and_reports_invalid_files` (not an object, wrong Version, bad hash, Task != stem, unreadable, absurdly nested JSON), `test_second_language_merges_into_the_same_file`, `test_same_language_twice_is_refused_and_nothing_changes`, `test_symlinked_specification_folder_is_refused` (copy the construction from the existing terms symlink test in `tests/test_spec_overlay.py`), `test_remove_deletes_only_that_task`, `test_load_without_a_folder_is_empty`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_spec_overlay_survey.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the three functions; write JSON with `indent=2, ensure_ascii=False` and a trailing newline like `write_local_terms`; check everything before writing anything.
- [ ] **Step 4: Run the tests.** Expected: PASS. Also `.venv/bin/python -m pytest tests/test_spec_overlay.py tests/test_spec_overlay_ops.py -q` (no regression).
- [ ] **Step 5: Commit** `feat(spec): a project's local survey fingerprints`.

---

### Task 3: `resolve` uses the project's fingerprints

**Files:**
- Modify: `src/survey_terms.py:225` (`resolve_survey_sidecar`)
- Test: `tests/test_survey_terms.py`

**Interfaces:**
- Consumes: `load_local_survey` (Task 2), `item_matches` (Task 1).
- Produces: `resolve_survey_sidecar(sidecar, library_dir=None, recipe_dir=None, project_root=None) -> dict`. Result keys stay `instrument` and `columns[{column, term, reason}]`; each column gains `source` (`"library"`, `"local"` or `""` when there is no term). New reason `language not registered`. Rules:
  1. Task in the library and item in its template: today's logic, source `library`. Exception: when the column's language is not among the languages the library item carries *and* the project has a local fingerprint for that task/item/language, the local fingerprint decides (source `local`); otherwise today's behaviour is unchanged.
  2. Task not in the library, project has a valid local file for it: instrument is `prism:<task>`; an item in the file is checked with `item_matches` (source `local`); an item not in the file is `unknown item`.
  3. Nothing knows the task: `unknown instrument`, as today.
  A local fingerprint never overrides a library result; `project_root=None` behaves exactly as before.

- [ ] **Step 1: Write the failing tests:** `test_project_only_task_resolves_from_local_fingerprints` (add fingerprints for a task absent from a tmp library; unchanged column gets `prism:<task>.<key>`, source `local`); `test_changed_wording_and_scale_keep_their_reasons`; `test_unregistered_language_gets_no_term`; `test_local_never_overrides_the_library` (task in tmp library with a different wording in the local file: library result wins); `test_local_german_works_with_a_library_english_task`; `test_without_project_root_nothing_changes` (existing expectations); `test_invalid_local_file_does_not_stop_resolve`. Use `library_dir=tmp_path` so no real library is read.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_survey_terms.py -q -k "local or fingerprint or unregistered"`. Expected: FAIL.
- [ ] **Step 3: Implement** the rules above in `resolve_survey_sidecar`; keep `_item_reason` untouched (library path).
- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_survey_terms.py tests/test_cli_terms.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(survey): resolve item IDs from a project's own fingerprints`.

---

### Task 4: CLI commands and docs

**Files:**
- Modify: `app/src/cli/parser.py` (the `spec local` subparsers near line 2298 and the `terms resolve` parser), `app/src/cli/commands/spec.py`, `app/src/cli/commands/terms.py:78` (`cmd_terms_resolve`), `app/src/cli/dispatch.py` if commands are listed there, `docs/CLI_REFERENCE.md` (around lines 1020 and 1035)
- Test: `tests/test_cli_spec.py`, `tests/test_cli_terms.py`, `tests/test_cli_dispatch_routing.py` (only if it needs the new names)

**Interfaces:**
- Consumes: `fingerprint_sidecar`, `write_local_survey`, `remove_local_survey`, `load_local_survey`, `resolve_survey_sidecar(..., project_root=)`.
- Produces:
  ```
  spec local add-survey    --project <p> --sidecar <file> [--language <code>] [--json]
  spec local remove-survey --project <p> <task> [--json]
  terms resolve            --modality survey --sidecar <file> [--project <p>] [--json]
  ```
  `add-survey` prints the task, the number of items and the languages written, and writes only the fingerprints (never item text). Errors (unreadable sidecar, `--language` not in the sidecar, same language already present, symlink) exit 1 with a message, as the other `spec local` commands do via `_fail`. `terms resolve` text output gains a fourth tab column, the source. The design lists `remove` extended; this plan uses a separate `remove-survey` instead (a term ID and a task slug are different arguments), and the design doc line is updated in this task.

- [ ] **Step 1: Write the failing tests:** in `tests/test_cli_spec.py` `test_add_survey_writes_fingerprints_without_item_text` (parse with `build_prism_tools_parsers`, run, read the file, assert none of the sidecar's description strings occur in it), `test_add_survey_second_language_merges`, `test_add_survey_refuses_a_language_the_sidecar_lacks`, `test_remove_survey`; in `tests/test_cli_terms.py` `test_resolve_with_project_uses_local_fingerprints` and `test_resolve_without_project_is_unchanged`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_cli_spec.py tests/test_cli_terms.py -q -k "survey or resolve"`. Expected: FAIL.
- [ ] **Step 3: Implement** the parsers and the two handlers (thin: read file, call `src/`, `_emit`/`_fail`); add `--project` to `terms resolve` and pass it through. Add the three commands to `docs/CLI_REFERENCE.md` in the style of the `spec local` block and note the new `source` column; change the design doc's "(existing command, extended)" line to `remove-survey`.
- [ ] **Step 4: Verify.** Run `.venv/bin/python -m pytest tests/test_survey_fingerprints.py tests/test_spec_overlay_survey.py tests/test_survey_terms.py tests/test_cli_spec.py tests/test_cli_terms.py tests/test_cli_dispatch_routing.py tests/test_spec_overlay.py tests/test_spec_overlay_ops.py -q` and `.venv/bin/python tests/verify_repo.py --check dual-tree-drift --no-fix`. Expected: all pass. Also run `find src -name survey_terms.py` and `python3 -c "import src.survey_terms as m; print(m.__file__)"` to confirm the edited file is the live one.
- [ ] **Step 5: Commit** `feat(spec): spec local add-survey and terms resolve --project`.

---

## Self-review

- Spec coverage: fingerprint format, equality, language rule, local file, merge order and `local` source, `add-survey` incl. `--language`, `language not registered`: Tasks 1 to 4. Not in Phase 1 by design: `propose --survey`, Contribute page, official file, acceptance script (Phases 2 and 3).
- Known divergence to confirm: fingerprint matches are exact (a missing min/max does not match), unlike the library path; the design says "exactly `_scale_matches`", which cannot be expressed as a hash.
