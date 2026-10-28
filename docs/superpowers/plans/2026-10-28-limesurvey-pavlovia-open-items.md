# LimeSurvey and Pavlovia: state and open items (2026-10-28)

Handoff note so the work can be picked up on another machine. Everything below is merged into `main` and
pushed unless it says "open".

## Done

**LimeSurvey import/export review** (merged, CI green): text cleaning, languages, fixed answers, row types
(checkbox/ranking/matrix/dual scale), import notes in the preview, one exporter builder, DBVersion 636 with
LimeSurvey 6 structural columns, response columns of a real LS6 archive (`SQ001-0/-1`), missing-items report,
padded numbers (`55.0000000000` -> `55`). Verified against real LimeSurvey 6 files (structure round trip 1:1).

**Pavlovia (SurveyJS) import** (`src/converters/pavlovia_import.py`): rating `rateMin/rateMax/rateStep/rateCount`,
texts given per language, matrix (one item per row), multiple text, "other"/"none" options, and import notes for
what cannot be represented (checkbox = several values in one column, ranking, expression, html blocks, hidden
items, choices from another question, unknown types). `pavlovia_questionnaire()` returns `(template, notes)`.

**Pavlovia responses** (`src/converters/pavlovia_responses.py`, CLI `survey prepare-pavlovia`): turns the
responses CSV into a wide table for `survey convert`. See `docs/CLI_REFERENCE.md` for the options. Decisions made
with the user for the first real survey: participant = `studyID` + `subID` zero-padded to 3 digits; session = the
text the participant saw; `question3`/`Raucher` read as `rauchen` (`--rename`); rows with answers are kept
whatever `isComplete` says; the survey default fills a field only for an experiment that never stores it.

**Template Editor**: the "Data Collection Software" group opens when `SoftwareVersion` is required and empty.

## Open

1. **SurveyJS export** (template -> survey `.json` in Pavlovia's format) with a round-trip check: export a template,
   re-import it, compare with the original survey (item names, rating values, choice labels, `visibleIf`,
   descriptions). The user loads the export in Pavlovia and compares it by eye; whether Pavlovia accepts an
   uploaded/pasted JSON is unverified. Not started; the user has not said yes yet.
2. **Studio page** for converting Pavlovia responses (only the command line exists). Logic is backend-only, so the
   page would be a thin adapter.
3. **Run the real conversion into the project folder.** Start with `survey convert ... --dry-run`. Decide the 5
   participant/session pairs with two different full attempts (`--duplicate-handling keep_first|keep_last`; the
   test run used `keep_last`). `survey convert` imports only the first session unless `--session all` is given.
4. **Intern checks** the LimeSurvey import/export; real data for a ranking question and an "Other" option on a
   multiple-choice question is still missing.
5. `Technical.SoftwareVersion` is required for Pavlovia but the survey file has no version (checked): it is typed
   in by hand (`--software-version`, or the editor field). Relaxing the rule would be a change in
   prism-specification.
6. Smaller: item IDs of checkbox/array rows with default `SQ001` codes are not consistently prefixed with the
   question code (the user said not to restructure item IDs); built-in answer labels exist in en/de only;
   `check_modalities.py` needs a `--terms` option upstream so the CI step can return to the plain script; the
   PsychoPy `.psyexp` export (`src/converters/pavlovia.py`) was never opened in PsychoPy and its FormComponent
   `items` is probably not a valid value (user does not use PsychoPy; leave unless asked).

## Test material (not in the repo)

`.claude/` is git-ignored. The real files used for the checks (a LimeSurvey 6 `.lsa`/`.lss` set, a Pavlovia survey
`survey-2.json` and its responses CSV with participant data) stay on the original machine and must be copied by
hand; never commit the responses. The tests use synthetic data shaped like the real files
(`tests/test_pavlovia_responses.py`, `tests/test_limesurvey_*.py`).
