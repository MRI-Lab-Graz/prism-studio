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
   `datestamp`). Incomplete responses are listed and left out by default. Rows are never merged.
2. **Review + override (C):** a per-response review table (date, completed, `lastpage`,
   assigned session or "left out"). Any row can be skipped (`skip`), given a session label
   (`session`), or, for an incomplete response, taken anyway (`include`: numbered by date
   among that participant's taken responses like a completed one; an `include` on a
   completed response does nothing).
3. **Persistence (A):** decisions are saved in the project, keyed by LimeSurvey's response
   `id` and scoped by survey (LimeSurvey numbers responses 1..N per survey), so they
   survive re-exports (new responses arrive over time).
4. **One implementation:** logic lives in the backend; CLI first, GUI only shows the
   result and writes through the same functions (golden rule).

Out of scope: exporting a cleaned `.lsa`, matching responses to MRI dates, time windows,
automatic merging of retries.

## Backend (`src/participants_sessions.py`)

`number_sessions_by_date(df, id_column, date_column="startdate", session_column="session",
decisions=None, response_id_column="id")` returns `(df, warnings)` as today, with:

- `df` containing only the responses that get a session (left-out rows removed);
- automatic labels from completed, non-overridden responses ordered by date;
- `decisions[response_id]` = `{"skip": true}`, `{"session": "<label>"}` (free-form
  string, compared exactly, never normalised) or `{"include": true}`; precedence: skip /
  label, then include, then completed;
- blocker `ValueError` when one participant ends up with the same label on two responses;
- an undated response that takes part in numbering is an error naming the participants
  (and the response ids when the response was included); if no response at all gets a
  session, `number_sessions_by_date` raises instead of returning an empty frame;
- warnings: a "Saved decisions applied: skipped ...; session 'x' for ...; included ..."
  line, left-out incomplete responses (count of reason `incomplete` only), participants
  without any taken response ("No completed response for: ..."), decisions for response
  ids not in the file, uneven session counts, the date column used.

`session_assignment_table(df, id_column, ..., decisions=None)` returns one row per
response: participant, response id, date, completed, lastpage, assigned session or
`None`, reason (`auto`, `override`, `incomplete`, `skipped`, `included`). The review
table, the CLI `review` output and the GUI table are all this list. The internal
session column used for numbering is never shown.

Decisions file: `code/session_assignments.json`,
`{"version": 2, "surveys": {"999999": {"responses": {"501": {"skip": true},
"502": {"session": "pre"}, "503": {"include": true}}}}}`. The survey key is the
LimeSurvey survey id read from the `.lsa` (`survey_<id>.lss`), else `"default"`
(`survey_id_of`). Helpers `load_session_assignments(project, survey_id)`,
`set_assignment(project, response_id, survey_id=, skip=|include=|session=)` (exactly one
of the three), `unset_assignment(...)`. A decision for a response id that is no longer in
the export is ignored (reported once as a warning).

## Command line

- `sessions review --input X.lsa --id-column token [--project P] [--json]`: prints the
  table, starting with `Survey: <id>` (also `survey_id` in the JSON).
- `sessions set --project P --survey 999999 --response 502 --session pre` / `--skip` /
  `--include`; `sessions unset --project P --survey 999999 --response 502`.
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
  endpoint). Per row: a Skip checkbox and a session-label input; each change is saved
  through the same helper (with the survey id the review returned) and the table reloads.
  The Skip box is checked exactly when the row gets no session, so incomplete rows start
  pre-ticked ("left out (incomplete)", muted). Unticking one saves `include`; ticking a
  completed row saves `skip`; reverting to the default removes the saved decision.
  The page only maps the checkbox to a decision payload.
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
- overrides: skip, explicit label, include an incomplete response (and include on a
  completed one is a no-op); duplicate label -> blocker; stale decision ignored with a
  warning; saved-decisions line; all-left-out error;
- decisions file round trip (per survey); `set`/`unset`; labels stay exact strings;
- CLI: `review --json`, `set`/`unset`, `survey convert` and `participants merge` honour
  the file;
- GUI e2e: disabled Session ID box in this mode, review table shows the rows with
  incomplete ones pre-skipped, unticking one includes it, skipping a completed row
  changes the preview.
