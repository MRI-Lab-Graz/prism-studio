# Session assignment review (repeated LimeSurvey responses)

## Problem

LimeSurvey has no session field. In a repeated-measures study the same token appears
once per wave, but also once per abandoned start. The first version of
`number_sessions_by_date` numbered every response, so a real archive
(24 responses, 10 participants) gets, for one participant, `ses-1..ses-7` from six
abandoned starts and one completed response; another participant (8 responses, none
completed) gets `ses-1..ses-8`. The user cannot see or correct what was assigned.

## Decisions (agreed)

1. **Default rule:** only *completed* responses (`submitdate` filled) become sessions,
   numbered `"1"`, `"2"`, ... per participant by date (`startdate`, falling back to
   `datestamp`). Incomplete responses are listed and left out. Rows are never merged.
2. **Review + override (C):** a per-response review table (date, completed, `lastpage`,
   assigned session or "left out"). Any row can be skipped, given a session label, or
   (for an incomplete response) included.
3. **Persistence (A):** decisions are saved in the project, keyed by LimeSurvey's response
   `id`, so they survive re-exports (new responses arrive over time).
4. **One implementation:** logic lives in the backend; CLI first, GUI only shows the
   result and writes through the same functions (golden rule).

Out of scope: exporting a cleaned `.lsa`, matching responses to MRI dates, time windows,
automatic merging of retries.

## Backend (`src/participants_sessions.py`)

`number_sessions_by_date(df, id_column, date_column="startdate", session_column="session",
decisions=None, response_id_column="id")` returns `(df, warnings)` as today, with:

- `df` containing only the responses that get a session (left-out rows removed);
- automatic labels from completed, non-overridden responses ordered by date;
- `decisions[response_id]` = `{"skip": true}` or `{"session": "<label>"}` (free-form
  string, compared exactly, never normalised);
- blocker `ValueError` when one participant ends up with the same label on two responses;
- warnings: left-out incomplete responses (count, participants with no completed response
  named), uneven session counts, the date column used.

`session_assignment_table(df, id_column, ..., decisions=None)` returns one row per
response: participant, response id, date, completed, lastpage, assigned session or
`None`, reason (`auto`, `override`, `incomplete`, `skipped`). The review table, the CLI
`review` output and the GUI table are all this list.

Decisions file: `code/session_assignments.json`,
`{"version": 1, "responses": {"501": {"skip": true}, "502": {"session": "pre"}}}`.
Helpers `load_session_assignments(project)`, `save_session_assignments(project, data)`,
`set_assignment(...)`, `unset_assignment(...)`. A decision for a response id no longer in
the file is ignored (reported once as a warning).

## Command line

- `sessions review --input X.lsa --id-column token [--project P] [--json]`: prints the table.
- `sessions set --project P --response 502 --session pre` / `--skip`;
  `sessions unset --project P --response 502`.
- `survey convert` and `participants preview|convert|merge` read the project's decisions
  file automatically, or `--session-assignments FILE`.

## Existing callers

- Participants import (`--sessions-from-date`, GUI checkbox) and survey conversion
  (`duplicate_handling="sessions"`) both pass `decisions` through to the one function.
- Survey conversion: the generated labels still go through the session map in a
  longitudinal project (unchanged); the typed Session ID is ignored in this mode.

## GUI (shows, never decides)

- With "Number as sessions by date" selected: the Session ID box is disabled with the
  note "Sessions are numbered 1, 2, ... by startdate (completed responses only)"; its
  REQUIRED badge turns neutral.
- A "Review session assignment" button opens the table (data from the same function via an
  endpoint). Per row: a skip checkbox and a session-label input; Save writes the decisions
  file through the same helper. Incomplete rows are muted.
- Preview summary line: "Sessions from startdate: N completed -> 1-K; M incomplete left
  out; participants without a completed response: ...". The internal `_dup_session_num`
  name is never shown.
- Changing the dropdown re-runs the session check so the session-map panel lists the real
  labels.

## Tests (TDD, written first)

Fixture mirrors the real archive: one participant with 7 responses and 1 completed, one
with 8 and none completed, one with 2 completed on different days.

- default rule: only completed responses get sessions; incomplete listed; no-completed
  participant named in the warning;
- overrides: skip, explicit label, include an incomplete response; duplicate label ->
  blocker; stale decision ignored with a warning;
- decisions file round trip; `set`/`unset`; labels stay exact strings;
- CLI: `review --json`, `set`/`unset`, `survey convert` and `participants merge` honour
  the file;
- GUI e2e: disabled Session ID box in this mode, review table shows the rows, saving a
  decision changes the preview summary.
