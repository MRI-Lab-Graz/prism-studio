# Methods section built from the imported data

## Intent

A researcher fills in project metadata first and imports real data (surveys,
scans) later. The methods section is a **draft for a scientific paper**: it must
state the *material* (every instrument and acquisition, with its metadata) and,
where it can be known, the *procedure* (which session contained what, in which
order). The researcher must not retype any of this into `project.json`; it is
read from what was imported.

Trigger: a project with only sociodemographics and survey data produced a methods
text with no survey information at all, because instruments were only described
when declared in `project.json` `TaskDefinitions`.

## Goals

1. **Material**: one entry per instrument found in the dataset (survey,
   biometrics), enriched from its template (name, citation, items, response
   format, license, ...); and per acquisition modality the device/sequence
   parameters already collected by `src/methods_acquisition.py`.
2. **Procedure**: a per-session description of what was collected, inferred from
   the dataset. Session order and timing are **inferred**, not asked for.
3. Honest gaps: when something is unknown, omit the sentence or leave a visible
   `[please add: ...]` placeholder. Never invent timing, durations or order.
4. One implementation in `src/` (CLI + GUI share `build_methods`); the GUI only
   calls it.
5. Cite PRISM Studio via the Zenodo concept DOI (done, 2026-10-21).

## Non-goals / anti-goals

- No new metadata form fields for survey/acquisition info.
- No claim of exact timing the data cannot support. A confident wrong paper is
  worse than a visibly incomplete draft.
- Session labels are free-form strings and are never normalized or coerced
  (CLAUDE.md). Matching is exact string comparison.
- Text-format files stay out of git-annex (CLAUDE.md); nothing new is written
  as an annexed file.

## What exists already

- `discover_tasks` (`src/methods_project.py`): surveys/biometrics found as
  `task-<name>` files are merged into `TaskDefinitions` for the text; declared
  entries win. Added 2026-10-21 with tests.
- `acquisition_summary` / `processing_summary`: scanner and device parameters.
- Generator: `generate_full_methods` in `app/src/reporting.py` (Procedure and
  Measures sections read `Sessions` and `TaskDefinitions` from `project.json`).

## Proposed behaviour (decisions as made in conversation)

- **Source of truth is the data files**, read at generation time. Import does not
  need to write anything into `project.json` for the text to be correct.
- **Sessions inferred from the dataset**: for each `ses-<label>` folder, list the
  instruments and acquisitions present and the number of participants that have
  them. Without session folders, one unnamed measurement occasion.
- **Timing inference** (best available, in this order):
  1. `acq_time` in `sessions.tsv` / `*_scans.tsv` when present: relative offsets
     from the first session ("about N days after baseline").
  2. Otherwise **order only**: sessions are named in a stable order and the text
     says nothing about intervals.
  Dates are scrubbed from MRI sidecars for privacy
  (`src/mri_json_scrubber.py`), so sidecars are not a timing source.
- Order of free-form labels is a **guess** (natural sort of the label). The text
  must not word it as fact when labels are non-numeric (e.g. `pre`, `post`):
  use "the sessions were" without ordinal claims, and flag in `warnings`.
- Optional: an explicit `Sessions` entry in `project.json` overrides inference,
  as today.
- Per-instrument participant counts come from the files actually present, so the
  text can state "n = 40 completed the X in session 1".

## Constraints

- TDD per CLAUDE.md; each new function gets its own test.
- Mind dual-tree drift: `app/src/reporting.py` is the live generator;
  `src/methods_project.py` is the single entry point. Verify with
  `python3 -c "import src.<mod> as m; print(m.__file__)"` before editing shared
  helpers.
- CLI parity: every behaviour reachable through `prism_tools` methods command
  with the same options as the GUI.
- Extract inference into small functions (`discover_sessions`, timing helper)
  rather than growing `generate_full_methods`.
- Run `ponytail:ponytail-audit` before merging.

## Left to the builder

- Exact sentence wording and the German variant (`lang="de"` exists).
- Data structure for the inferred session summary (suggestion: a dict like
  `acquisition_summary`'s, injected into `generate_full_methods`).
- How to sort labels while never altering them.

## Open for the user

- Where `[please add]` placeholders should appear in the GUI preview versus
  exported files (assumed: both, so nothing is silently dropped).
