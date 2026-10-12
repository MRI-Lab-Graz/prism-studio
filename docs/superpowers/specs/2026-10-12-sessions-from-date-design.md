# Sessions from acquisition date (repeated LimeSurvey measures)

## Problem

LimeSurvey has no session indicator. In a repeated-measures study the same
participant ID (e.g. `token`) appears once per wave, so the participants import
fails ("non-unique values for the selected ID column 'token'") or keeps only the
first non-empty value. Survey conversion has `duplicate_handling="sessions"`, but
it numbers repeats in file order, not by date, and it is blocked in longitudinal
projects.

## Decision

Number each participant's responses by acquisition date: earliest = `"1"`,
next = `"2"`, ... These are raw session labels; in a longitudinal project the
existing session map (`code/session_map.json`) must still map every one of them
(e.g. `"1" -> "pre"`), so nothing is invented.

Order only. No time windows, no automatic merging of retries or incomplete runs:
the tool flags them and the PI cleans up the data in LimeSurvey.

Out of scope: matching survey responses to MRI acquisition dates (possible
later feature on top of this one).

## Backend (`src/participants_sessions.py`)

```python
number_sessions_by_date(df, id_column, date_column="startdate") -> (df, warnings)
```

- Stable sort by `id_column`, then by `pd.to_datetime(date_column)`. If
  `date_column` is `"startdate"` and a row's value is empty, use that row's
  `datestamp`.
- Adds a `session` column: per ID, `"1"`, `"2"`, ... (strings). If the source
  already has a `session` column, stop with an error (never overwrite).
- A row whose date is still missing or unparseable: `ValueError` naming the
  IDs/rows. The function cannot order it, so it does not guess.
- Rows are never dropped or merged.
- Warnings (list of strings):
  - every ID with an incomplete run (empty `submitdate`, when that column
    exists), with its session label and `lastpage`;
  - when IDs have different session counts, the distribution
    (e.g. `80 IDs x 2 sessions, 12 x 1, 3 x 3`).
- Session labels are compared and stored as exact strings (repo rule).

## Participants import

- CLI: `--sessions-from-date [COLUMN]` (default `startdate`) on the
  participants convert/merge commands.
- `ParticipantsConverter` / backend: when set, call `number_sessions_by_date`
  after loading the source, then hand the result to the existing session
  handling with `session_column="session"` (session pick, session map, merge
  session resolution). Warnings go into the returned messages.
- GUI: a checkbox "Sessions from acquisition date" next to the ID column; it
  only passes the option through to the same backend call (no JS logic).

## Survey conversion

- `duplicate_handling="sessions"` uses `number_sessions_by_date` when the
  source has `startdate` or `datestamp`; otherwise it keeps the current
  file-order numbering.
- Remove the `SessionMapError` that blocks `"sessions"` in longitudinal projects
  (`app/src/converters/survey.py`): the generated labels go through the session
  map like any other raw label, and unmapped labels still fail conversion.

## Tests (TDD, written first)

- `number_sessions_by_date`: date ordering independent of file order; incomplete
  run warning; count distribution warning; missing date -> error;
  `datestamp` fallback; existing `session` column -> error.
- Participants import of a repeated-ID `.lsa`/CSV with the option: one row per
  ID per session, no "non-unique" error.
- Survey conversion in a longitudinal project with `"sessions"`: labels mapped
  through the session map; an unmapped label fails.
