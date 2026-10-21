# Survey dates for session timing, and survey info in the methods draft

Builds on `2026-10-21-methods-from-imported-data-design.md`.

## Intent

The methods draft should state the time between sessions and describe each survey
(language, version, administration, completion time). Timing needs per-subject dates,
which PRISM discards at import today (only `SurveyDuration` and the time of day are
kept). Dates are identifying, so the same change must guarantee they never leave the
lab in a shared export.

## Decisions (from the user)

1. Store the survey start **date** in each survey TSV at import; compute session
   intervals from it.
2. The date must be **removed** when the dataset is made publicly available.
3. Survey info for the draft starts with the assistant's proposal (below).

## Goals

- **Import**: the LimeSurvey import writes `SurveyStartDate` (`YYYY-MM-DD`, from
  `startdate`, falling back to `datestamp` as `participants_sessions.py` does) next to
  `SurveyStartTime`; sidecar entry injected exactly like `SurveyStartTime`
  (`src/converters/limesurvey.py`, both injection sites).
- **Timing**: `add_session_timing` computes **per subject** the days from that
  subject's earliest session to each later session, then takes the median across
  subjects. Sources, first that yields data: `SurveyStartDate` in survey TSVs,
  `sessions.tsv` `acq_time`, `*_scans.tsv` `acq_time`. (Today it compares medians
  of absolute dates; per-subject differences are the correct quantity.)
- **Privacy gate**: `SurveyStartDate` is removed (column in every survey TSV and its
  sidecar entry) from `export_project` (always, whether or not `anonymize` is on, because with it off the
  ZIP would otherwise carry dates) and from
  `export_project_to_plain_folder`, which is how data leaves the lab as a plain copy.
  A test fails if any exported survey TSV still has the column.
- **Survey info in the text** (assistant's proposal, user said "start with it"), per
  instrument, only when known: language (`Technical.Language`), version/variant used
  (`Study.Version`), administration (`Technical.AdministrationMethod`,
  `Respondent`, `SoftwarePlatform`), and **mean completion time** (mean, SD, n) from
  `SurveyDuration` across the project's survey TSVs for that task.

## Non-goals / anti-goals

- No dates from any other converter; Excel/CSV imports have no start date and keep the
  `[please add: time between sessions]` placeholder.
- No retroactive dates for already-imported datasets (re-import adds the column).
- No subscale text: no template field carries it (assistant's call; revisit if the
  template gains one).
- A shared dataset must never contain a survey date. If the gate and a convenience
  conflict, the gate wins.
- `publish_to_server` (internal lab server, plain git) is unchanged: dates stay on the
  internal server, which is already the documented place for non-public data.
- Session labels stay free-form; no normalisation.

## Constraints

TDD; CLI/GUI parity (`build_methods` stays the single entry point; export options
unchanged); dual-tree check for `app/src/web/export_project.py` vs `src/`; text-format
files stay out of git-annex; run `ponytail:ponytail-audit` before merge.

## Left to the builder

Wording of the survey-info sentences; where the date-stripping helper lives (one
function used by both exports); how to read `SurveyDuration` efficiently for large TSVs.

## Assistant's calls (check these)

- Plain-folder export strips the date too, although it has no anonymize switch.
- `acq_time` already present in `sessions.tsv`/`scans.tsv` is **not** stripped by this
  change (existing behaviour, BIDS allows it); say if it should be.
- Zip export strips the date unconditionally (ruling made at plan time; the anti-goal
  "a shared dataset never contains a survey date" cannot hold otherwise).
- Time of day (`SurveyStartTime`) is kept; the date is what identifies.
