# Project required-fields gate and Timepoints as shared info

Date: 2026-10-15. Status: draft for review.

## Intent

A user may save an unfinished project page, but may not work with the
project until the required fields are set. The user is told about this at
save time. Separately, `StudyDesign.Timepoints` (`single` / `multiple`)
becomes project-level info that every importer reads, so a single-timepoint
project gets the simple import path wherever possible.

## Current state (read from code)

- `StudyDesign.Timepoints` is read only by `src/session_map.py`
  (`project_timepoints`, `session_map_for_conversion`), used by the survey/LSA
  converter and the participants/sociodemographics converter.
- `multiple`: every session label needs an exact entry in
  `code/session_map.json`. `single`: no gate. `undeclared`: survey import
  fails only if the data carries sessions.
- physio, biometrics, eyetracking, environment and file-management ignore
  Timepoints; each has its own `--session*` options.
- "Required" (creation-blocking) fields are `Basics.Name/Authors/Keywords`
  and `StudyDesign.Timepoints` (`CREATION_BLOCKING_FIELDS` in
  `projects_metadata_helpers.py`, duplicated in `metadata.js`). Nothing blocks
  tools on an incomplete project.

## Design

### 1. Readiness rule (backend, once)

New `src/project_ready.py`:

- `missing_required_fields(project_path) -> list[str]`: `[]` when there is no
  `project.json` (not a PRISM project, no gate) or all required fields are
  filled. Source of truth for the field list is one Python constant;
  `metadata.js` receives it from the backend instead of keeping a copy.
- `ProjectNotReadyError(missing)` with one user-facing message, reused by CLI,
  Flask and the save banner.

### 2. Enforcement at two choke points

- CLI: one check in `dispatch_prism_tools` (`app/src/cli/dispatch.py`), project
  path resolved from the command's arguments. Non-zero exit with the message.
  Exempt: project commands, `session-map`, `environment`, `--help`.
- GUI: one Flask `before_request` for tool API routes, HTTP 409 with the
  missing-fields list. Exempt: Projects-page routes. The GUI only displays the
  message.
- No project addressed and none active: not gated. A project that is
  addressed or open is gated.
- New tools are blocked by default; exemptions are an explicit allow-list.
- Old projects with empty `Timepoints` become blocked (intended). The
  `undeclared` special case in `session_map` becomes unreachable and is
  removed.

### 3. Telling the user at save time

The Projects-page save response carries `missing_required` (same function).
When non-empty the page shows a persistent banner: "Saved. Tools are blocked
until these are filled: Authors, Timepoints." A blocked tool shows the same
text with a link back to the Projects page.

### 4. Timepoints as shared import info

One helper, `project_timepoints()` (already exists), is the only reader.
Every importer asks it instead of its own heuristics:

- `single`: the session is fixed (no `ses-` level or one default session, per
  BIDS rule already used by the project); no session column, session picker,
  session map or assignment review is shown or required. Session options on
  CLI and GUI are hidden / rejected as unnecessary, not guessed.
- `multiple`: session label required for every import, mapped via the session
  map (existing behavior), extended to physio, biometrics, eyetracking and
  environment importers.
- Importer-by-importer rollout: survey and participants already honor it;
  physio, biometrics, eyetracking, environment follow. Each gets its own
  small change and test; the rollout order is decided in the plan.

Open point for the plan: exact `single` behavior per importer (default
session label vs. no session level) must match what those converters write
today; verify against existing outputs before changing.

### 5. Tests (TDD, tests first)

- Unit: `missing_required_fields` (no project, complete, each field missing).
- CLI: blocked project exits non-zero for a tool command; exempt commands run.
- Flask: 409 and exemptions; save response carries `missing_required`.
- JS: banner shown after incomplete save.
- Parity: JS and Python required-field lists cannot drift.
- Per importer: `single` skips session handling, `multiple` demands a map.

## Out of scope

Changing the Projects pages' own save behavior (save stays allowed);
migrating existing project data; new session features beyond using Timepoints.
