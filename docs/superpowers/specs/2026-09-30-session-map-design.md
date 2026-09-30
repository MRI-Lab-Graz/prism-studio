# Session map for longitudinal projects

Status: draft for review. Nothing is implemented.

## Problem

Session labels are free-form strings (`1`, `01`, `pre` are three different labels; see CLAUDE.md).
Different sources of one study name the same timepoint differently (the MRI export says `T0`, the
survey says `pre`). Today the survey converter takes whatever the user types and the participants
importer picks one session from a column. Nothing forces the user to state, once and explicitly, how
source labels become the session names in the dataset.

## Decisions (agreed 2026-09-30)

1. **Explicit only, never autofill.** PRISM never guesses, orders, numbers or suggests a session
   name. No "did you mean", no pre-filled target fields.
2. **Strict.** In a longitudinal project *every* source label needs a map entry, even `1 -> 1`.
   The map is the only source of session names in filenames.
3. **Many-to-one is allowed.** `T0 -> 1` and `pre -> 1` may both exist (different sources, same
   session). Two entries with one target is the user's deliberate choice, not an error.
4. **Extend on demand.** A label not in the map blocks the import and is named in the message;
   the user adds it (once per new timepoint). Mapped labels pass through, so earlier imports are
   never blocked again.
5. **Existing data is never rewritten.** The map only affects future imports.
6. **CLI parity.** The same gate and the same map work from the command line.

## Required project field

A new **required** study-metadata field states whether the study has one timepoint or several.
It is separate from `StudyDesign.Type`, which cannot answer this (a cohort study or a trial can be
single- or multi-session).

- Field: `StudyDesign.Timepoints`, values `single` (cross-sectional) or `multiple` (longitudinal).
- Required for project creation like the other required fields (Projects page).
- `single`: no map; behaviour as today.
- `multiple`: the session-map gate applies.
- Existing projects without the field: the first session-bearing import asks the user to declare
  it (no default, no inference from the data).

## Data

`code/session_map.json`, a flat object of source label to target label:

```json
{"pre": "1", "T0": "1", "post": "2"}
```

- Lives in `code/` because it is a conversion input (like `code/library`), not part of what is
  shared. The declaration itself lives in `project.json` and is shared with the study metadata.
- Text file: never git-annex (project text policy).
- Source labels compare by exact string (`session_label` in `src/participants_sessions.py`, which
  only turns spreadsheet floats like `1.0` into `1`). No case folding, no zero padding.
- Target must be a valid BIDS label: letters and digits, non-empty. Integers are a convention, not
  enforced.

## Backend (single implementation)

One module, e.g. `src/session_map.py`, no Flask imports:

- `load_session_map(project_root) -> dict[str, str]`
- `save_session_map(project_root, mapping)` (validates targets)
- `unmapped_labels(labels, mapping) -> list[str]`
- `apply_session_map(label, mapping) -> str`, raising a `SessionsNotMappedError` that lists every
  unmapped label at once.

The survey converter and the participants importer call these; neither carries its own rule. Other
converters can adopt the same calls later.

## CLI

- `prism_tools session-map show`
- `prism_tools session-map set <label> <target>`
- Conversion commands fail in a `multiple` project with the list of unmapped labels.

## GUI

A "Session mapping" panel (Converter, shown when the project is `multiple`): detected source labels
listed with **empty** target inputs; saving writes `code/session_map.json` through the backend. The
Convert/Preview buttons stay disabled, with the missing labels as the hint, until every detected
label is mapped. For the participants importer, the picked "one session for everybody" is mapped
through the same function.

Warning only (never acts): if the detected labels contain both `1` and `01`, say so and leave both
to be mapped by the user.

## Testing (TDD)

- Unit (pytest) for the backend module: exact matching, `1` vs `01`, many-to-one, invalid target,
  all unmapped labels reported together, float artifact.
- vitest for the gate rule (which route needs the map), like `sessionChoiceBlockReasonForRoute`.
- Browser flows (tests/e2e): unmapped label blocks Convert and names the label; mapping unblocks;
  `pre`/`T0` both to `1` land in `ses-1`; a `single` project is unaffected.
- CLI test: failure message lists unmapped labels; `set` then convert succeeds.

## Out of scope

- Auto-detecting or ordering timepoints.
- Rewriting already converted data.
- Biometrics, physio, eye-tracking and environment converters (they adopt the same function later).

## Open points for review

- Field name and values (`StudyDesign.Timepoints`: `single`/`multiple`).
- Whether the map also needs a per-source dimension later (e.g. "MRI" vs "survey" tables). Not
  needed while many-to-one entries are allowed in one flat file.
