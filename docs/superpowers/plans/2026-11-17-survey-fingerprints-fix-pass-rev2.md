# Survey Fingerprints, Phase 1 Fix Pass (revision 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the built local half of survey fingerprints in line with design revision 2 before the branch merges: looser text normalization, answer labels in the per-language wording hash, and `local:` names for project-only instruments.

**Architecture:** Two small changes in code that already exists: `src/survey_fingerprints.py` (what is hashed) and `resolve_survey_sidecar` in `src/survey_terms.py` (which prefix a project-only match gets). No new module, no new command, no format version change (`Version` stays 1: nothing has been shared, so existing local files written on this branch must be re-added; nothing is migrated).

**Tech Stack:** Python stdlib (`hashlib`, `json`, `unicodedata`), pytest.

**Spec:** `docs/superpowers/specs/2026-11-17-survey-fingerprints-design.md` (revision 2: sections "Fingerprints", "Names before acceptance").

## Global Constraints

- THE RULE: logic stays in `src/`; no Studio route exists for this (nothing in Studio calls `resolve_survey_sidecar`).
- Do not edit vendored files (`official/library/**`, `app/schemas/**`, `scripts/specification/**`). The mapping check that refuses non-`prism:` IDs lives in the vendored scripts and is a specification-PR item, not part of this pass.
- Hash canonical form is unchanged: `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, SHA-256 hex.
- Text normalization (every text that is hashed: `Description` and level labels): Unicode NFKC, then `casefold()`, then every character whose Unicode category starts with `P` replaced by a space, then whitespace collapsed (`" ".join(text.split())`). (Builder call: replace by space, not delete, so `well-being` and `well being` match.)
- Wording hash input per language: `{"Description": <normalized>, "Labels": {<code as str, integer-valued floats as int>: <normalized label>}}`. Labels come from `Levels` in that language (a label that is a plain string belongs to the sidecar's language; a label that is a `{lang: text}` object contributes one text per language). A language that has a `Description` but no labels hashes `"Labels": {}`. A language that has labels but no `Description` gets no wording hash (an item without a Description is matched on its scale alone, as before).
- The scale hash is unchanged (codes, MinValue, MaxValue; no labels).
- `local:` prefix: only the IDs of a task **no library template has** become `local:<task>.<item>`; `instrument` becomes `local:<task>`. A library item matched by a local fingerprint for a language the library lacks keeps its official `prism:` ID (the ID is the library's). `source` values are unchanged (`library`, `local`, `""`).
- TDD: each task starts with a failing test. Subagents run on Sonnet 5.5, model set explicitly.
- Branch `feat/survey-fingerprints`. The ponytail audit, code review and security review already ran on the earlier commits; run a scoped re-review of this pass's commits before merge.

## Review Focus

- Two typings of one item must match: curly vs straight quotes, `–` vs `-`, upper vs lower case, a trailing full stop, a non-breaking space.
- A reversed scale (same codes, labels `1 = never` / `2 = always` vs `1 = always` / `2 = never`) must give `changed wording`, with the same scale hash.
- Labels that are a plain string, a `{lang: text}` object and absent must all hash without error; a label that is not a string (a number, null) is skipped, never a crash.
- An item whose `Description` is missing still matches on scale alone, even when it has labels.
- A library task with a local German fingerprint keeps `prism:`; a project-only task gets `local:`.
- Two items whose texts differ only by punctuation or case now match each other: accepted (the scale must match too); do not add a test that forbids it.

## File Structure

- Modify `src/survey_fingerprints.py`: `normalize_text`, `wording_hashes`, `item_matches`, `fingerprint_sidecar`.
- Modify `src/survey_terms.py`: the two places in `resolve_survey_sidecar` that build `prism:` IDs and the `instrument`.
- Modify tests: `tests/test_survey_fingerprints.py`, `tests/test_survey_terms.py`, `tests/test_cli_terms.py`, `tests/test_spec_overlay_survey.py` (only if a fixture there breaks).
- Modify `docs/CLI_REFERENCE.md` (the `terms resolve` / `add-survey` paragraph).

### Task 1: Normalization and labels in the wording hash

**Files:**
- Modify: `src/survey_fingerprints.py`
- Test: `tests/test_survey_fingerprints.py`

**Interfaces:**
- Consumes: `_texts`, `_collapse`, `_NOT_ITEMS`, `_slug` from `src/survey_terms.py` (unchanged).
- Produces: `normalize_text(text) -> str`; `wording_hashes(item: dict, language: str) -> dict[str, str]` (**signature change**: takes the whole item, not the description; callers are `fingerprint_sidecar` and `item_matches` only, plus the tests); `item_matches(entry, column, language)` and `fingerprint_sidecar(sidecar, language=None)` keep their signatures.

- [ ] **Step 1: Write the failing tests** in `tests/test_survey_fingerprints.py`. Replace the three assertions of the existing normalization test and the dict test so they call `wording_hashes({"Description": ...}, "en")`, and add:
  - `test_normalize_text`: `normalize_text("  I don’t FEEL fine… – really. ")` equals `normalize_text("i don't feel fine - really")`; `normalize_text("well-being") == normalize_text("well being")`; `normalize_text("Ａ")` equals `normalize_text("a")` (NFKC).
  - `test_two_typings_of_one_item_match`: two items with `Description` `"I feel “sad”."` and `"i feel \"sad\""`, same `Levels`: `item_matches(entry_from_first, second, "en") == ""` where `entry_from_first = fingerprint_sidecar(...)["Items"]["Q1"]`.
  - `test_reversed_scale_is_changed_wording`: items with equal `Description` and `Levels` `{"1": "never", "2": "always"}` vs `{"1": "always", "2": "never"}`: `scale_hash` equal, `item_matches(...) == "changed wording"`.
  - `test_labels_in_every_shape`: `Levels` with a plain-string label, a `{"en": "a", "de": "b"}` label, and a numeric label `5`; `wording_hashes` returns without error, one hash per Description language; the numeric label is skipped.
  - `test_item_without_description_still_matches_on_scale`: no `Description`, labels present: `wording_hashes(...) == {}` and `item_matches` returns `""` for an equal scale.
- [ ] **Step 2: Run** `pytest tests/test_survey_fingerprints.py -q`. Expected: FAIL (`normalize_text` not defined, signature mismatch).
- [ ] **Step 3: Implement** `normalize_text(text) -> str` per Global Constraints; implement `wording_hashes(item, language)` building the per-language input above (reuse `_texts` for the `Description`; one small helper for the labels per language); update `fingerprint_sidecar` and `item_matches` to pass the whole item/column. `_texts` still collapses whitespace; `normalize_text` runs on its result.
- [ ] **Step 4: Run** `pytest tests/test_survey_fingerprints.py tests/test_spec_overlay_survey.py tests/test_survey_terms.py -q`. Expected: PASS. Any test that hard-coded an old hash value is updated to compute it with the function instead.
- [ ] **Step 5: Commit** `fix(survey): looser text normalization and level labels in the wording hash`.

### Task 2: `local:` names for project-only instruments

**Files:**
- Modify: `src/survey_terms.py` (`resolve_survey_sidecar`), `docs/CLI_REFERENCE.md`
- Test: `tests/test_survey_terms.py`, `tests/test_cli_terms.py`

**Interfaces:**
- Consumes: `item_local_id(task, key)` (unchanged), `item_matches` (Task 1).
- Produces: `resolve_survey_sidecar` returns `term` `local:<task>.<item>` and `instrument` `local:<task>` for a task without a library template; everything else as before.

- [ ] **Step 1: Write the failing tests.** In `tests/test_survey_terms.py` change the project-only assertion at the current line 331 to expect `"local:mine.q1"` and add `assert out["instrument"] == "local:mine"`; add `test_library_item_in_a_local_language_keeps_prism_id` asserting the case at the current line 362 still gives `prism:tipi.tipi02` with `source: "local"`. In `tests/test_cli_terms.py` add a test that a project-only sidecar (task not in the library) run through `spec local add-survey` and `terms resolve --project` prints `local:<task>.<item>` in the text and JSON output; the existing `DEMO01` test (a library task) must keep `prism:demo.demo01`.
- [ ] **Step 2: Run** `pytest tests/test_survey_terms.py tests/test_cli_terms.py -q`. Expected: the new/changed assertions FAIL.
- [ ] **Step 3: Implement** in the `template is None` branch: `term = f"local:{item_local_id(task, key)}"`; and `instrument = f"local:{task}"` when `template is None and local`, `f"prism:{task}"` when a template exists. Do not touch the library branch.
- [ ] **Step 4: Update `docs/CLI_REFERENCE.md`**: in the `terms resolve` paragraph say that a task only the project has gets `local:` names (not official, not frozen), that the wording hash ignores case, punctuation and quote style, and that it includes the answer labels. Run `pytest tests/test_survey_fingerprints.py tests/test_spec_overlay_survey.py tests/test_survey_terms.py tests/test_cli_terms.py tests/test_cli_spec.py tests/test_cli_dispatch_routing.py -q`. Expected: PASS except the two known `tests/test_cli_spec.py` failures that only occur in a worktree without `.venv` (confirm they pass in the main checkout).
- [ ] **Step 5: Commit** `fix(survey): project-only instruments resolve to local: names`.

## Self-review

- Spec coverage: normalization, labels in the wording hash, `local:` prefix, `Version` stays 1 (revision 2, "Fingerprints", "Names before acceptance"). The mapping check refusing non-`prism:` IDs, discovery by hash, records, lifecycle, IRI, SKOS/SSSOM and `TermURL` retirement are specification-PR and Studio-PR items (design "Phases and PRs", items 2 and 3), not this pass.
- Type consistency: `wording_hashes(item, language)` is the only signature change; both callers are named in Task 1.
