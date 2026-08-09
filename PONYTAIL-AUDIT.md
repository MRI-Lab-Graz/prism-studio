# Ponytail Audit — prism-studio (pass 2, 2026-08-09)

Repo-wide over-engineering scan. Scope: complexity/bloat only — correctness,
security, and performance are out of scope for this pass.

> **Note:** this pass ran via isolated git worktrees checked out from the last
> commit. The fixes applied in pass 1 (see bottom of this file) are still
> uncommitted in the working tree, so the worktrees audited the pre-fix
> codebase for `src/` and `app/src/`. That doesn't invalidate the findings
> below — they're all in code pass 1 didn't touch — but it's worth
> committing pass-1's fixes before trusting a future pass's "already fixed,
> don't re-flag" instructions at face value.

## Findings (ranked, biggest cut first)

1. `native:` Two separate hand-rolled YAML-text builders reinventing PyYAML
   (already a dependency) for `CITATION.cff`.
   Replace both with `yaml.safe_dump(data, sort_keys=False,
   allow_unicode=True)`.
   - `app/src/project_manager.py:8496-8657` (~160 lines)
   - `src/converters/anc_export.py:685-835` (~150 lines)

2. `delete:` `app/static/js/shared/storage.js` is entirely dead —
   `getLocalStorage`/`setLocalStorage`/`removeLocalStorage` are re-exported
   through 4 barrel files but never actually imported by any real consumer;
   `clearLocalStorage`/`getSessionStorage`/`setSessionStorage`/
   `removeSessionStorage`/`clearSessionStorage` aren't even re-exported.
   Delete the file and its 4 re-export lines.
   - `app/static/js/shared/storage.js:1-145`

3. `delete:` `app/static/js/shared/api.js`'s `apiGet`/`apiPost`/`apiPut`/
   `apiDelete`/`apiUpload` CRUD wrappers have zero callers anywhere in the
   repo (`template-editor.js` defines its own local `apiGet`/`apiPost`
   instead). Only `fetchWithApiFallback`/`fetchWithRelativePathFallback`/
   `installApiFetchFallback` from this file are actually used.
   - `app/static/js/shared/api.js:163-283`

4. `delete:` `scripts/normalize_official_templates.py` is a self-described
   "one-off migration" (renames `Study.Abbreviation`→`Study.ShortName`,
   `Study.NumberOfItems`→`Study.ItemCount`). Zero remaining legacy keys
   anywhere in `official/library/survey/`; script referenced nowhere (no
   docs, no CI, no other code). Migration already ran.
   - `scripts/normalize_official_templates.py:1-65`

5. `delete:` `anonymize_dataset()` is unused outside its own test — every
   real caller (`app/src/web/export_project.py`,
   `app/src/cli/commands/anonymize.py`) calls the lower-level
   `create_participant_mapping`/`anonymize_tsv_file`/
   `replace_participant_ids_in_text`/`update_intendedfor_paths` building
   blocks directly instead.
   - `src/anonymizer.py:332-379`

6. `yagni:` Two competing CLI dispatch mechanisms exist. `dispatch_command()`
   (generic `Mapping[str, handler]` dispatcher) is exported from
   `src.cli.__init__` and covered only by its own dedicated test file; the
   actual CLI entrypoint calls `dispatch_prism_tools()` instead — a 130-line
   hardcoded if/elif chain. Delete one.
   - `app/src/cli/dispatch.py:15-32` (unused generic dispatcher)
   - `app/src/cli/entrypoint.py:104` (the if/elif chain actually wired up)

7. `delete:` Duplicate `_sanitize_answer_code_for_ls` +
   `_LS_ANSWER_CODE_MAX_LENGTH` reimplemented in `survey.py` despite
   `survey.py` already importing `survey_processing` (used elsewhere in the
   same file). Use `_survey_processing._sanitize_answer_code_for_ls`
   instead.
   - `app/src/converters/survey.py:177,191-214`
   - cf. `app/src/converters/survey_processing.py:85-96`

8. `delete:` Duplicate `sanitize_id()` reimplemented in
   `cli/commands/convert.py`, byte-identical to `utils/naming.py`'s version
   already imported elsewhere (`survey.py`, `project_registration.py`).
   - `app/src/cli/commands/convert.py:26-45`
   - cf. `app/src/utils/naming.py:21-35`

9. `shrink:` `_normalize_run_entity`'s "strip run- prefix, regex-strip
   non-alnum, re-prefix run-\<label\>" logic independently reimplemented 3x
   with only edge-case handling differing. Consolidate to one shared
   helper.
   - `app/src/converters/survey_core.py:120`
   - `app/src/converters/survey_io.py:73`
   - `app/src/web/blueprints/conversion_utils.py:121`

10. `shrink:` `_deep_merge` dict-merge algorithm reimplemented twice with
    identical semantics (merge if both dict, else override wins).
    Consolidate to one shared helper.
    - `app/src/validator.py:238-251`
    - `app/src/web/blueprints/tools_helpers.py:256-265`

11. `shrink:` `sync_survey_keys.py` and `sync_biometrics_keys.py` are ~90%
    identical key-synchronization functions, differing only in the library
    subfolder, template filename, and two small policy flags. Consolidate
    into one `_sync_library_keys(library_dir, template_filename, *,
    reset_study_values, skip_item_prefix)` called by two ~10-line wrappers.
    - `src/maintenance/sync_survey_keys.py:1-89`
    - `src/maintenance/sync_biometrics_keys.py:1-84`

12. `shrink:` `inspect_pyreadstat_write_support()` and
    `inspect_pandas_support()` are near-line-for-line duplicates (same
    bundle-glob / `importlib.import_module` / except / namespace-stub
    shape). Extract one `_inspect_module_support(module_name, key_attrs,
    bundle_glob)` helper.
    - `src/runtime_dependencies.py:10-137`

13. `shrink:` The "try import, except ImportError: bootstrap sys.path,
    retry same import" pattern is duplicated three times back-to-back for
    three different import groups. Collapse into one
    `_import_with_bootstrap()` retry helper.
    - `src/converters/limesurvey.py:38-87`

14. `yagni:` `pollJobStatus()`'s customization hooks `getLogs`/
    `getNextCursor`/`isDone`/`isSuccess` are never overridden at any of 7
    call sites — only `getFailureError` is ever passed, and only to swap a
    default string. Inline the 4 unused hooks' default bodies and replace
    `getFailureError` with a plain `failureMessage` string.
    - `app/static/js/shared/job-polling.js:21-25,83-91`

15. `shrink:` `escapeHtml`/`escapeHtmlForOption` reimplemented (same
    regex-replace chain) in 7+ files instead of importing the canonical
    export in `shared/dom.js`. Two have zero barrier to importing (they
    already import other `shared/*.js` helpers) — pure copy-paste-not-import
    miss, and `escapeHtmlForOption`'s copies are missing the `'` escape vs.
    the canonical version (a latent inconsistency, not just duplication).
    - `app/static/js/modules/converter/survey-convert.js:1987`
    - `app/static/js/modules/converter/biometrics.js:198`
    - lower priority, needs module-conversion: `template-editor.js:248`,
      `index.js:99`, `file_management.js:454`,
      `survey-customizer.js:1736`, `survey-generator.js:122`

16. `shrink:` `_create_bidsignore` builds output via 12 chained `content +=`
    calls. Replace with `"\n".join([...])` over one list literal.
    - `app/src/project_manager.py:6803-6832`

17. `native:` `parse_lsa_responses()` extracts `<fieldname>` values via a raw
    regex pass over the XML bytes immediately before/after parsing the same
    content with `ET.fromstring()` — redundant with
    `resp_root.findall(".//fieldname")`.
    - `src/converters/limesurvey.py:172-173`

**`net: ~-900 lines, -0 deps possible.`**

## Considered and rejected (false positives, for the record)

- `web/utils.py::sanitize_jsonable` vs `web/reporting_utils.py::sanitize_jsonable`
  — not a duplicate; it's the documented dual-tree PyInstaller-fallback
  delegation pattern (see `CLAUDE.md`).
- `limesurvey_exporter.py::_sanitize_answer_code` — genuinely different
  algorithm from the reverse-lookup functions above (forward truncation
  with uniqueness-collision handling vs. reverse matching); docstring
  correctly documents them as mirrors.
- `schema_manager.py`'s `parse_version`/`is_compatible_version` — bespoke
  compatibility rules (major must match exactly, minor may be higher) not
  equivalent to stdlib/installed-package semver comparison.
- `reporting.py::_md_to_html` — hand-rolled Markdown→HTML, but no markdown
  package is in `requirements*.txt`; flagging it would mean adding a
  dependency, the opposite of a `native:` finding.
- `orcid_lookup.py`'s hand-rolled `urllib` client instead of `requests` —
  carries deliberate SSRF-hardening (URL/host/scheme validation,
  `# nosec`/`# noqa: S310`); security-adjacent design, out of scope.
- `SurveyWorkflowStageService` / `BidsEntityParser` — single-instantiation
  classes that could be plain modules, but each used across 4-6 files with
  real shared state; style preference, not confident enough to flag.
- Route-wrapper pattern in `app/src/web/blueprints/` (`def api_x(): return
  _x()` after `@blueprint.route(...)`) — looks like passthrough bloat but is
  required test-seam plumbing (`patch.object(module, "_x")` needs the late
  name lookup at call time). Confirmed by breaking 11 tests when tried in
  pass 1.

## Also assessed and deliberately left alone (not bloat)

- `scripts/future_feature/build_environment_from_survey.py` and
  `scripts/future_features/homebrew/` — maintainer-documented roadmap
  placeholders (each has a "Future Feature" README; the survey script is
  referenced with a full usage example in `docs/CLI_REFERENCE.md`).

## Pass 1 fixes already applied (uncommitted, in working tree)

- Deleted 6 dead backward-compat aliases + 5 dead optional-import shims in
  `conversion.py`.
- Cleaned unused imports/locals across ~15 blueprint files.
- Deleted 3 unused `ItemRegistry` methods + tests.
- Deduped `_extract_terminal_suffix_label` (`mri_json_scrubber.py` ↔
  `project_export_helpers.py`).
- Deleted 3 dead `text_sanitizer` functions + the redundant
  `sanitize_question_text` wrapper + tests.
- Swapped hand-rolled file-compare for `filecmp.cmp` in `batch_convert.py`.
- Swapped hand-rolled UUID/deep-clone for `crypto.randomUUID()` /
  `structuredClone()` in 3 JS files.
- Consolidated 4 duplicated `read_json`/`write_json` reimplementations onto
  `src/utils/io.py`'s canonical versions.
- Added `_curl_json_post` helper for the 3 functions in
  `backend_monitoring.py` that genuinely shared that curl-JSON-POST shape.
- **Skipped:** `scripts/future_feature/*` (documented roadmap, not dead) and
  collapsing the 17 passthrough routes in `conversion.py` (reverted — broke
  11 tests, see note above).

Net so far: ~-600 lines removed, full test suite at the same 4 pre-existing
failures as before pass 1 started.
