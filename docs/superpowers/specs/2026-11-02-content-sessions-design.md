# Content sessions (per-participant session order)

## Problem

PRISM names the sessions of a multi-timepoint project by time: repeated LimeSurvey
responses are numbered `1`, `2`, ... by date per participant
(`number_sessions_by_date`, see `2026-10-12-sessions-from-date-design.md` and
`2026-10-12-session-assignment-review-design.md`), and one global map
(`code/session_map.json`, e.g. `"1" -> "pre"`) names them, the same for everyone.

Some studies are organised by content instead: a crossover with `sleepdep` and
`rested` sessions in counterbalanced (often random) order. Participant A's first
response is `sleepdep`, participant B's first is `rested`. A global map cannot
express this, and LimeSurvey stores only dates, so the condition cannot be read
from the data. The lab has the order (randomisation list, RA notes); PRISM needs a
place to record it per participant.

## Decisions (agreed)

1. **Declared in the project.** New field `StudyDesign.SessionLabels`: `time` | `content`,
   asked when `Timepoints` is `multiple`.
2. **Future studies only.** Required when a project is set up with `multiple`
   timepoints. An existing `multiple` project without the field behaves as `time`
   (today's behaviour) and is not blocked; the user may add the field later.
3. **Order still comes from the `.lsa`.** Date numbering, the review table and the
   skip/include/session decisions stay exactly as they are.
4. **`time`:** nothing changes, the global session map names the numbers.
5. **`content`:** a per-participant order map names the numbers
   (`sub-01: 1 -> sleepdep, 2 -> rested`). It is filled either from a prepared file
   or in Studio. Both go through the same backend functions and write the same
   project file; the CLI has matching commands (THE RULE).
6. **Never guessed.** In a `content` project, a participant without an entry, or with a
   numbered response that has no entry, stops the import with a list of who/what is
   missing (same strictness as the session map today). PRISM never generates or
   randomises an order.

## Project metadata

- `app/schemas/stable/project.schema.json` (and `v0.2`; the `project` schema is not
  vendored, so it is edited here): `StudyDesign.SessionLabels`, enum `["time", "content"]`,
  description explaining both.
- Projects page (`study_metadata.html`, `metadata.js`): a select next to Timepoints,
  shown and required only when Timepoints is `multiple`. Project setup is the GUI-only
  exception, so requiring it at creation/save time is UI validation of the form.
  The select carries a visible explanation (agreed), e.g.:
  *Time: sessions are waves in the same order for everyone (ses-1, ses-2 or pre/post).
  Content: sessions are conditions whose order differs per participant (e.g. sleepdep /
  rested in counterbalanced order); you then provide each participant's order, and the
  folders are named after the condition (ses-rested, not ses-2).*
  The same explanation appears in the schema description and in `docs/CLI_REFERENCE.md`
  for `session-order`.
- `src/project_ready.py` gate: **unchanged** (decision 2). An absent field is `time`.
- `src/session_map.py`: `project_session_labels(project_path) -> "time" | "content"`
  (absent with `multiple` -> `time`; a present but invalid value is an error, never
  silently `time`; with `single` timepoints the field is ignored, single wins).

## Order map (backend, new `src/session_order.py`)

File: `code/session_order.tsv` (plain text, never annexed; already covered by the
DataLad text policy for `.tsv`).

```
participant_id	session_number	session
P01	1	sleepdep
P01	2	rested
P02	1	rested
P02	2	sleepdep
```

- `participant_id` (agreed): the ID **as LimeSurvey has it** (the raw value of the ID
  column, e.g. `token`), which is what the lab's randomisation list and the review table
  (`session_assignment_table`) show. Compared exactly. The survey path, which numbers
  by the normalized `sub-<label>` (`normalize_sub`, incl. `subject_id_match`), must look
  up by the raw ID of the response; the builder keeps the raw ID alongside the
  normalized one for that. A `sub-P01` written in the file is accepted as `P01`
  (strip one leading `sub-`, nothing else).
- `session_number`: the date-order number as `number_sessions_by_date` produces it
  (`"1"`, `"2"`, ...), compared as an exact string.
- `session`: the session name, letters and digits only (same rule as session-map targets).
- Errors on load (reported with line numbers, file not used): missing columns, a
  duplicate (`participant_id`, `session_number`), one participant with the same `session`
  twice, an invalid `session` name.

Functions (one implementation, used by CLI and Studio):
`load_session_order`, `save_session_order` (atomic write like `save_session_map`),
`set_order_entries(project, participant, {number: session})`,
`remove_order_entries(project, participant[, numbers])`,
`import_session_order(project, file)` (reads a prepared TSV/CSV/XLSX with the three
columns, validates it, then replaces or merges; merge is the default, `--replace` replaces),
`apply_session_order(participant, number, order) -> session` (raises
`SessionsNotOrderedError` naming participant + number).

## Where it applies

Only to sessions **numbered by date**: survey conversion with
`duplicate_handling="sessions"` and participants import with `--sessions-from-date`.
In a `content` project those numbers go through the order map instead of the global
session map.

- **Survey conversion:** numbered responses get `ses-<name from order map>`.
  `project_registration` (`_output_session_id_fn`) and the template-version override
  normalizer (`_MappedSessionNormalizer.for_override`) must know the resolved names, so
  project.json records `ses-sleepdep`, not `ses-1`, and template-version selections by
  content name are accepted.
- **Participants import (Claude's call):** numbers are replaced by names *before*
  filtering and splitting, so split columns are `age@ses-sleepdep`, and `--session
  sleepdep` picks each participant's response whose resolved name is `sleepdep`. `time`
  projects keep today's behaviour unchanged (out of scope).
- **Review overrides (Claude's call):** in a `content` project a `{"session": "<label>"}`
  decision is the final content name (`sleepdep`), not looked up in the order map. The
  duplicate-label check runs *after* names are resolved, so an override `sleepdep` plus an
  order-map `sleepdep` on the same participant is a blocker naming both responses.

**Count mismatch (agreed: detect, correct manually).** Numbering is per file, so one
project-wide order map can mislabel a participant who is missing a wave in one survey
(their `1` in survey B is really their second session). Rule: for each participant in a
`content` import, the number of numbered responses (not counting those with a
`{"session": ...}` override or `skip`) must equal the number of their order-map entries.
If not, stop before writing, list each participant with "N responses in this file, M in the
session order", and point to the review table, where the user names those responses
directly (`sessions set --session sleepdep` / the session-name input). Once every
response of that participant in the file is overridden or skipped, the check passes for
them. The review table shows the mismatch per participant.

Imports that carry their own session labels (a session column, a typed Session ID,
physio, biometrics, environment, batch) keep using the global session map in both modes;
a content project maps e.g. `sleepdep -> sleepdep` there as today.

The check runs before anything is written, collecting every missing
(participant, number) into one error, like `require_sessions_mapped`.

## Command line

- `session-order show --project P [--json]`
- `session-order set --project P --participant sub-01 --number 1 --session sleepdep`
- `session-order unset --project P --participant sub-01 [--number 1]`
- `session-order import --project P --file order.xlsx [--replace]`
- `sessions review` (existing) gains the resolved session name per row in a `content`
  project, so the CLI shows the same thing as Studio.

Handlers are thin adapters in `app/src/cli/commands/` like `session_map.py`.

## Studio (shows, never decides)

In a `content` project, where the session-mapping panel appears today (Converter,
Survey and Sociodemographics tabs), show the order panel instead:

- Upload a prepared file -> `import_session_order` (same function as the CLI).
- A table, one row per participant of the current import x numbered session (data from
  the review endpoint), with a session-name input per cell; each change is saved through
  `set_order_entries`. Suggestions in the input are the session names already used in the
  order map (a datalist; no logic).
- Missing entries are highlighted from the backend's error list; the convert button stays
  blocked the same way it is for an unmapped session today.

## Parity and tests (TDD, written first)

- `session_order`: load/save round trip, every load error, merge vs replace import,
  exact-string comparison (`1` != `01`), invalid session name.
- `project_session_labels`: absent -> `time`, invalid -> error.
- Survey conversion of a repeated-response `.lsa` fixture in a `content` project: two
  participants with opposite orders land in `ses-sleepdep`/`ses-rested` correctly; a
  missing participant fails with all gaps listed; a `{"session": ...}` decision wins;
  override clash after resolution is a blocker; count mismatch stops and passes once
  the participant's responses are overridden; IDs match LimeSurvey's raw ID and
  `sub-`-prefixed entries; project.json records content names; same project as `time`
  still uses the global map.
- Participants import with `--sessions-from-date` in a `content` project: split columns
  `age@ses-sleepdep`, `--session sleepdep` picks per participant; `time` unchanged.
- `tests/test_cli_studio_parity.py`: Studio upload/set and CLI import/set write the same
  `code/session_order.tsv`; conversion output identical.
- `tests/test_importers_use_session_policy.py`: still holds (the order map is part of the
  session policy, not a new bypass).

## Non-goals

- Generating or randomising an order.
- Inferring condition from dates, time windows or survey content.
- Changing existing projects or making the field required in the readiness gate.
- Content mode for imports that already carry session labels.

## Left to the builder

File layout inside `src/session_order.py`, error message wording, exact panel layout,
how the review endpoint exposes the resolved name.
