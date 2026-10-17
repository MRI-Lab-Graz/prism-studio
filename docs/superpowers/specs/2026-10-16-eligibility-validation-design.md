# Eligibility criteria checked by the validator

## Problem

A study states who may take part (age 18-35, no left-handers, IQ at least 85)
in its metadata. Nothing checks the collected data against it. Researchers
want to learn about out-of-criteria participants **while data is still being
collected**, not at the end. Typing the same limits again in the
sociodemographics panel is not acceptable (double entry).

## Decision

Limits are entered **once**, as structured criteria in the project metadata.
The sociodemographics panel only **links** a column to a criterion. The
validator reads limits from the metadata and warns for each participant
outside them. Warnings only, never errors.

## Goals

- Criteria for standard variables (NeuroBagel terms) and for any other
  variable ("Other measure": IQ, VO2max, ...). Both are stored identically.
- Useful on a partial dataset: run it after every few participants.
- Change the limit in the metadata and the next validation uses it; no
  re-mapping.
- Works from the command line with the same options as the GUI.

## Non-goals

- No errors, nothing blocks saving or converting.
- No per-participant state stored anywhere; every validation recomputes.
- The free-text `InclusionCriteria` / `ExclusionCriteria` stay as they are,
  for criteria nobody can check automatically ("normal vision").
- No generated free text, no sample-size progress check, no multi-column
  rules ("age 18-35 AND female").

## Data model

`project.json`, `Eligibility.Criteria` (new list; schema in
`app/schemas/stable/project.schema.json`):

```json
{"id": "age", "label": "Age", "term": "nb:Age", "type": "numeric",
 "mode": "include", "min": 18, "max": 35, "unit": "years"}
{"id": "no-male", "label": "Sex", "term": "nb:Sex", "type": "categorical",
 "mode": "exclude", "values": ["Male"]}
{"id": "iq", "label": "IQ", "term": null, "type": "numeric",
 "mode": "include", "min": 85, "unit": "points"}
```

- `id`: unique, stable, what the sociodemographics link points to.
- `term`: a NeuroBagel term from the fixed list (Age; Sex, Handedness,
  Group/Diagnosis, Education level as categorical), or `null` for "Other
  measure". Type and, for categorical terms, the allowed values come from the
  term's vocabulary in `src/neurobagel.py`.
- numeric: `min` and/or `max`, both inclusive, either may be missing.
  `include` flags values outside the range; `exclude` flags values inside it.
- categorical: `values` are **labels** (Male), never raw codes.

`participants.json`, on the column: `"EligibilityCriterion": "<id>"`. Only the
link. Limits are never copied into it.

## Validator

New check on `participants.tsv`, run with the normal validation. One WARNING
per participant per criterion, naming the participant, the value and the
limit, e.g. `sub-P012: age 17 is outside inclusion range 18-35 years
(criterion: Age)`. A summary count comes first so 40 violations stay readable.

- Empty/`n/a` values are skipped (data may be incomplete).
- Categorical: the raw code is translated to its label through the column's
  `Levels`. No `Levels` on a linked categorical column: one warning that the
  criterion cannot be checked, then skip.
- Linked column missing from `participants.tsv`: one warning.
- A criterion with no linked column: silent.
- Non-numeric value in a numeric column: skip (the data-type checks already
  report it).

Logic lives in one new backend module under top-level `src/` (imported as
`src.<name>`), called from the validator. New warning code documented in
`docs/ERROR_CODES.md`.

## Metadata form (Projects page)

In the Eligibility section: a list of criteria rows. Add row: pick the
term (fixed list plus "Other measure"), include/exclude, then range inputs
(numeric, with unit) or value tick boxes (categorical). "Other measure" asks
for a name, unit and range. Projects pages are exempt from the CLI rule.

## Sociodemographics panel

Per column a select: *Eligibility criterion: none / Age / IQ / ...*.
Pre-selected when the column's NeuroBagel term equals a criterion's term;
the user confirms. For "Other measure" criteria the user picks by hand. The
panel shows the criterion's unit beside the column's unit and warns when both
are known and differ. Backend function decides the pre-selection; the panel
only renders it.

## CLI

No new flag. `participants convert` and `participants merge` already copy any
extra per-column key of `--neurobagel-schema` into `participants.json`, so
`--neurobagel-schema '{"age": {"EligibilityCriterion": "age"}}'` writes the
link and the GUI panel sends it the same way. A test pins this. `participants
preview --json` additionally returns the suggested links. Validation is
already a CLI command and picks the check up automatically.

## Constraints

- Follow CLAUDE.md: test first, logic in the backend, GUI is an adapter,
  check dual-tree resolution for every touched `app/src/` file.
- Session labels and codes stay exact strings; no normalization.
- Replace import drops annotations today; links go with them. The existing
  Replace confirmation text must say so. Merge keeps links of existing
  columns.

## Calls made without asking (my choices)

- Bounds are inclusive and either may be missing, so "exclude IQ below 70" is
  `exclude, max 69`.
- One warning per participant per criterion, no cap.
- A criterion with no linked column is silent.
- Categorical checks ship second; the data model above already holds them.

## Build order

1. Schema + backend check for numeric criteria (tests first).
2. CLI flag and link writing.
3. Panel select with auto-preselect; metadata form rows.
4. Categorical criteria via `Levels`.
5. Docs: ERROR_CODES, projects and converter_participants pages, an
   assignment-folder example (age 18-35 on the FitCog data).

## Tests (written first)

- Numeric include/exclude, open-ended bounds, inclusive edges.
- Empty and non-numeric values skipped; missing linked column; unlinked
  criterion silent.
- Limit change in `project.json` changes the next result without touching
  `participants.json`.
- Merge keeps links; Replace drops them and says so.
- CLI flag writes the link; panel pre-selection matches the backend function.
- Categorical via `Levels`; missing `Levels` warns once.
