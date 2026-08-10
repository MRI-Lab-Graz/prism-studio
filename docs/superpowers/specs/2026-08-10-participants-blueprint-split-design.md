# Design: Split `conversion_participants_blueprint.py`

Date: 2026-08-10
Status: Approved (shape), pending implementation plan

## Problem

`app/src/web/blueprints/conversion_participants_blueprint.py` is 2,748 lines,
42 helper functions and 9 routes. Two route handlers dominate it:
`api_participants_preview` (393 lines) and `api_participants_convert` (275
lines), with `api_participants_convert_start` (193 lines) close behind. This
was flagged as the #2 monolith in a repo-wide assessment (alongside
`project_manager.py`, `#1`, out of scope here).

The codebase already has precedent for splitting this exact blueprint:
`app/src/web/blueprints/conversion_participants_helpers.py` (634 lines)
already holds template/relevance-filtering and neurobagel-schema-generation
helpers, imported by the blueprint via `from .conversion_participants_helpers
import ...`. This design continues that established
`conversion_participants_<concern>.py` naming convention rather than
introducing a new structural pattern (e.g. a nested package).

## Root-cause finding

While reading the two big handlers, found that `api_participants_convert`'s
`mode == "file"` branch (lines 2251–2320) and `_run_participants_convert_job`'s
`mode == "file"` branch (lines 2612–2705) — the synchronous route and the
async job-worker thread body — contain near-byte-for-byte duplicated logic
for writing `participants.tsv`/`participants.json` (NeuroBagel schema
rekey/merge, fallback descriptions, file writes). A second, smaller
duplication: the `force_overwrite`/`existing_files` guard block is repeated
verbatim between `api_participants_convert` (lines 2148–2169) and
`api_participants_convert_start` (lines 2422–2440).

This is exactly the drift risk this repo has been bitten by before (see
`CLAUDE.md`'s `src/` vs `app/src/` notes) in miniature: two independently
maintained copies of the same business logic, one of which will silently go
stale the next time someone fixes a bug in only one of them. Consolidating
these is in scope for this refactor, not just moving code around.

## Scope

- **In scope:** `app/src/web/blueprints/conversion_participants_blueprint.py`
  only (backend). Confirmed via `python3 -c "import
  src.web.blueprints.conversion_participants_blueprint as m; print(m.__file__)"`
  that this file has no `src/`-side mirror and is the live module — no
  namespace-package drift risk for the existing file.
- **Out of scope:** `ParticipantsConverter`/`_write_survey_participants` in
  `app/src/converters/survey.py` (converter core), and
  `app/static/js/modules/converter/participants.js` (frontend). Both were
  explicitly deferred by the user to a later pass.
- **Out of scope:** `project_manager.py` (repo's #1 monolith) and the rest of
  `app/src/converters/survey.py` — separate efforts.

## Target file layout

All five files are flat siblings in `app/src/web/blueprints/`, matching the
existing convention (`conversion_physio_handlers.py`,
`conversion_environment_handlers.py`, `conversion_participants_helpers.py`
already live this way — no nested package).

### `conversion_participants_blueprint.py` (kept, shrinks to ~9 thin routes)
- `conversion_participants_bp` Blueprint object, `_participants_job_store`
- `_get_session_project_root`
- The 9 route functions: `save_participant_mapping`, `api_participants_check`,
  `api_participants_detect_id`, `api_participants_preview`,
  `api_participants_merge`, `api_participants_merge_conflicts`,
  `api_participants_convert`, `api_participants_convert_start`,
  `api_participants_convert_status`
- Each route becomes: parse request → call one or two helpers from the
  modules below → build response. No inline business logic.

### `conversion_participants_io.py` (new)
Upload handling, file reading, and format-diagnostic helpers:
`_save_participants_upload_to_temp`, `_normalize_separator_option`,
`_expected_delimiter_for_suffix`, `_read_participants_input_table`,
`_get_excel_sheet_metadata`, `_resolve_participants_sheet_arg`,
`_classify_time_style`, `_detect_mixed_time_style_columns`,
`_format_mixed_time_style_message`.

Plus one new function extracted from `api_participants_preview`'s exception
handler (lines 1810–1881): `_diagnose_preview_error(exc, df, input_path,
suffix, sheet_arg, separator_option, preview_stage)` — the mixed-time-format
diagnostic fallback, currently inlined in the route's `except` block.

### `conversion_participants_mapping.py` (new)
Schema/column-mapping helpers: `_normalize_column_token`,
`_rekey_neurobagel_schema_to_output_columns`, `_canonicalize_preview_id_column`,
`_parse_requested_column_list`, `_resolve_excluded_output_columns`,
`_collect_preview_column_values`, `_load_existing_participants_schema`,
`_load_saved_participants_mapping`, `_normalize_legacy_participants_mapping`,
`_resolve_web_participant_import_mapping`.

Plus one new function extracted from `api_participants_preview`'s inline
additional-columns block (lines 1668–1735):
`_resolve_additional_preview_columns(df, project_root, excluded_columns,
extra_columns_json)` — merges columns from the saved participants mapping
JSON with frontend-supplied `extra_columns`, honoring exclusions.

### `conversion_participants_merge.py` (new)
Unchanged in substance, moved as-is:
`_build_participants_merge_schema_preview`, `_project_relative_merge_paths`,
`_parse_participants_merge_request`, `_participants_id_required_response`,
`_validate_participants_merge_request_context`,
`_build_existing_participants_preview_payload`,
`_convert_existing_participants_files`.

### `conversion_participants_convert.py` (new)
`_run_participants_convert_job` (the async job-worker thread body), plus two
new functions that eliminate the duplication found above:

- `_write_participants_outputs(project_root, input_path, mapping,
  converter_separator, sheet_arg, participants_tsv, participants_json,
  neurobagel_schema, log_msg) -> dict` — the consolidated TSV/JSON writer
  (NeuroBagel rekey/merge, fallback descriptions, file writes, success
  payload). Both `api_participants_convert`'s `file` branch and
  `_run_participants_convert_job`'s `file` branch call this instead of each
  carrying their own copy.
- `_check_existing_participants_files(project_root, mode, force_overwrite) ->
  (existing_files, error_response_or_None)` — the repeated 409 guard block
  from `api_participants_convert` / `api_participants_convert_start`.

## Testing approach

Two tiers, matching CLAUDE.md's "extract and add a dedicated test" rule and
the TDD skill already in effect for this session:

1. **Regression net for the move-only parts:** the ~19 existing participants
   tests in `tests/test_web_blueprints_conversion.py` plus
   `tests/test_participants_converter_edge_cases.py` /
   `test_participants_converter_extra.py` must stay green, unmodified,
   throughout. These exercise the routes end-to-end and are the proof that
   pure code-motion didn't change behavior.
2. **New TDD test for the real behavior change:** `_write_participants_outputs`
   is a genuine consolidation (two implementations become one), not a move —
   per TDD, write a failing test first (small df + mapping + neurobagel
   schema in a tmp project dir, assert the two output files and their
   contents) before extracting the function, confirm it fails for the right
   reason (function doesn't exist yet), then extract and make it pass. Same
   treatment for `_check_existing_participants_files`.

## Explicitly deferred (not this pass)

- `ParticipantsConverter` / `_write_survey_participants` (converter core)
- `app/static/js/modules/converter/participants.js` (frontend)
- Any behavior change beyond consolidating the two duplicated write paths —
  this is a structural refactor, not a feature change.
