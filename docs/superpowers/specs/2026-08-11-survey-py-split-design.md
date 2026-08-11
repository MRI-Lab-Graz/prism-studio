# Design: Split the three oversized functions in `survey.py`

Date: 2026-08-11
Status: Approved, pending implementation plan

## Problem

`app/src/converters/survey.py` is 3,800 lines. Three functions account for
most of its bulk and were flagged as the #2 (converter core) item in a
repo-wide monolith assessment, after the participants blueprint split
(`docs/superpowers/specs/2026-08-10-participants-blueprint-split-design.md`,
already merged):

- `_convert_survey_dataframe_to_prism_dataset` — 668 lines (line 1519–2185)
- `_map_survey_columns` — 371 lines (line 2274–2643)
- `_write_survey_participants` — 225 lines (line 2742–2966)

Unlike the participants blueprint, `survey.py` is not a flat blob — it
already delegates heavily to sibling modules that exist for exactly this
purpose: `survey_core.py` (662 lines), `survey_io.py` (1,159 lines),
`survey_lsa.py` (358 lines), `survey_participants_logic.py` (352 lines),
`survey_templates.py` (1,400 lines), `survey_processing.py` (941 lines).
`survey.py`'s established role is to be the top-level orchestrator that
ties these together; the three oversized functions above are where that
boundary broke down — either through incomplete extraction (the
orchestrator) or because a self-contained algorithm was never split out in
the first place (the other two).

## Dual-tree drift check

`src/converters/survey.py` is a symlink to `app/src/converters/survey.py`
(confirmed via `ls -la`), matching the `excel_base.py` precedent documented
in `CLAUDE.md`. No drift risk for this file — editing
`app/src/converters/survey.py` is live through both import paths.

## Scope

All three functions, in the same effort (the user chose the larger scope
over splitting just the worst offender). `app/prism-studio.py`,
`project_manager.py` (the #1 monolith from the original assessment), and
the frontend JS converter modules are explicitly out of scope — separate
efforts.

## What each function actually looks like

### `_convert_survey_dataframe_to_prism_dataset` (668 lines)

Already an orchestrator. What remains inline, in order:

1. **Validation & setup** (~40 lines) — argument validation, path
   resolution, `task_value_offsets` normalization. Stays inline; this is
   genuine top-level orchestration.
2. **Four nested closures** (~65 lines) — `_normalize_sub_id_raw`,
   `_normalize_sub_id` (closes over a `_subject_id_match` built from
   `project_path` via `build_subject_id_matcher`/`load_existing_participant_ids`),
   `_normalize_ses_id`, `_normalize_run_id`, `_is_missing_value`. These are
   then threaded through nearly every downstream call in the function as
   `normalize_sub_fn=`/`normalize_ses_fn=`/etc. keyword arguments.
3. **Load Aliases and Templates** (~50 lines) — alias file loading,
   `ParticipantsConverter` template loading/comparison, template
   preprocessing via `_load_and_preprocess_templates`.
4. **LSA Structural Matching** (~60 lines) — a loop over
   `lsa_analysis["groups"]` that classifies each group (participants /
   high-confidence match / medium-confidence match / unmatched) and calls
   into `_survey_lsa` helpers per branch, raising `UnmatchedGroupsError` if
   anything is left unmatched.
5. **Column/session determination, ID mapping, dedup, collision check,
   participant-registry warning** (~130 lines) — a mix of already-delegated
   calls (`_resolve_selected_tasks`, `_resolve_id_and_session_cols`,
   `_apply_subject_id_mapping`, `_detect_sessions`,
   `_filter_rows_by_selected_session`, `_handle_duplicate_ids`) interleaved
   with inline logic (wide-format-column rejection, LimeSurvey
   system-column extraction, a case-insensitive ID collision check,
   participant-registry-warning construction).
6. **Column mapping + task/run resolution** (~60 lines) — calls
   `_map_survey_columns`, `_resolve_tasks_with_warnings`,
   `_build_col_to_task_and_task_runs`, an inline run-number-detection block,
   `_build_task_context_maps`.
7. **Results prep + dry-run early return** (~60 lines).
8. **Write output** (~135 lines) — directory setup, description write,
   participants write (via `ParticipantsConverter.write_participants`),
   task sidecars, response processing/writing, value-offset bookkeeping,
   LimeSurvey system-variable writing, `.bidsignore` update, final result
   construction. Already mostly delegated to `_survey_io`.

Target after extraction: ~150–250 lines of pure sequencing, matching the
participants blueprint's "route becomes thin orchestrator" outcome.

### `_map_survey_columns` (371 lines)

Fully self-contained — no delegation to any sibling module today. Four
sequential phases sharing local state (`col_to_mapping`, `task_run_tracker`,
`unknown_cols`/`filtered_unknown`, `warnings`, `near_match_candidates`,
`near_match_applied`):

1. Exact column-to-template matching (~65 lines).
2. Near-match candidate detection when items don't exactly match templates
   — the largest, most intricate sub-algorithm (~125 lines): builds
   per-task primary-item/alias/normalized-item lookups, finds single-target
   near-match candidates, filters them to full one-to-one item-count
   matches per task, rejects duplicate targets.
3. Applying approved near-matches, subject to an optional task filter
   (~70 lines).
4. Final per-task run-number computation and unknown-column handling
   (unknown_mode: error/warn/ignore) (~30 lines).

### `_write_survey_participants` (225 lines)

Called via `ParticipantsConverter.write_participants` (a thin pass-through
method) from step 8 above. Also fully self-contained. Phases:

1. Load `participants_mapping.json` if present; log what was found.
2. Determine which source columns to include — two modes: explicit mapping
   (only mapped columns) vs. template-only (only columns matching the
   official participant template, with an LSA-mangled-name fallback).
3. Build the output dataframe: apply value mappings/missing-value handling,
   normalize/rename the ID column, dedupe by participant, auto-correct
   values against the template.
4. Merge with an existing `participants.tsv` on disk if one exists —
   a distinct, self-contained algorithm (outer-join old/new, prefer new
   non-missing values, fall back to old).
5. Write `participants.tsv` and `participants.json`.

## Target file layout

- **`survey_core.py`** (grows): `build_survey_id_normalizers(project_path) ->
  SurveyIdNormalizers` replaces the four closures with one factory
  returning a small dataclass of callables (`normalize_sub`, `normalize_ses`,
  `normalize_run`, `is_missing`) — needed because the current closures
  capture `_subject_id_match`, itself built from `project_path`, so a plain
  set of standalone functions can't replace them without still taking
  `project_path` (or the matcher) as a parameter; a factory keeps the call
  site in the orchestrator a single line instead of four. Also gets
  `_load_survey_aliases_and_templates(...)` for phase 3 above.
- **`survey_lsa.py`** (grows): `_apply_lsa_structural_matching(...)` wraps
  the phase-4 loop, keeping its existing raise-on-unmatched behavior.
- **`survey_participants_logic.py`** (grows): `_write_survey_participants`
  moves here wholesale (not just its internals — it has no existing
  delegation to build on, and its logical siblings, like
  `_apply_subject_id_mapping`, already live here), split internally into
  `_determine_participant_output_columns(...)`,
  `_build_participant_output_dataframe(...)`,
  `_merge_with_existing_participants_tsv(...)`. `survey.py` imports the
  top-level function back in, matching this module's existing
  qualified-call convention (`_survey_participants_logic.<name>`) — the one
  call site inside `ParticipantsConverter.write_participants` changes from
  a bare local call to a qualified one, nothing else about that method
  changes.
- **New file `survey_column_mapping.py`**: `_map_survey_columns` moves here
  wholesale (same reasoning as above), split internally into
  `_match_columns_to_templates(...)`, `_find_near_match_candidates(...)`,
  `_apply_approved_near_matches(...)`. `survey.py` imports the top-level
  function back in.
- **`survey.py`**: keeps `_convert_survey_dataframe_to_prism_dataset` as
  the orchestrator (now calling out to all of the above instead of
  inlining), plus everything not covered by this plan (the public API
  functions, `ParticipantsConverter`, `SurveyResponsesConverter`, and the
  many smaller already-fine-sized helpers).

## Testing approach

Two tiers, matching the participants blueprint plan and this session's TDD
requirement:

1. **Regression net for pure moves:** the existing suite exercising the
   public entry points (`convert_survey_xlsx_to_prism_dataset`,
   `convert_survey_lsa_to_prism_dataset`) — `tests/test_web_blueprints_conversion.py`,
   `tests/test_survey_preview_regressions.py`,
   `tests/test_lsa_import_integration.py`,
   `tests/test_converter_project_save_contracts.py`,
   `tests/test_cli_survey_commands_remaining.py`,
   `tests/test_survey_value_offsets.py`,
   `tests/test_hostile_demo_pipeline.py`,
   `tests/test_survey_converter_version_plan_acq.py`,
   `tests/test_hostile_survey_pipeline.py`,
   `tests/test_survey_template_version_persistence.py`,
   `tests/test_unicode_normalization_consistency.py` (~12,000 lines total)
   — must stay green, unmodified, throughout. None of the three functions
   have direct unit tests today (confirmed by grep — they're only reached
   indirectly), so this is the only existing safety net for the move
   itself.
2. **New TDD test per extracted function:** every new function boundary
   introduced above (`build_survey_id_normalizers`,
   `_load_survey_aliases_and_templates`, `_apply_lsa_structural_matching`,
   the three `_write_survey_participants` phases, the three
   `_map_survey_columns` phases) gets a dedicated failing-test-first unit
   test, per `CLAUDE.md`'s extract-and-test rule. The near-match detection
   algorithm inside `_map_survey_columns` is the highest-value target for
   this — it's the most intricate, least-obviously-correct piece of logic
   in scope, and currently has zero direct coverage.

## Explicitly deferred (not this pass)

- `app/prism-studio.py`, `project_manager.py` — separate efforts.
- Frontend JS converter modules.
- Any behavior change — this is a structural refactor only.
