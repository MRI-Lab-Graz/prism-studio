# Proposing a New Modality

PRISM describes data belonging to a subject as a data file plus a JSON sidecar.
Surveys, biometrics, physiology and the other modalities all follow this
principle, and so can yours (for example blood samples drawn alongside MRI).

New modalities are added to PRISM itself: you propose one, a maintainer
registers it, and it ships with the next release.

## What you need

1. The workbook `official/create_new_modality/modality_proposal_template.xlsx`
   (it opens in Excel, LibreOffice and Numbers).
   - Sheet `Modality`: `Name`, `Suffix`, `Extensions`, `Description`.
     Give the name of an existing PRISM modality (for example `biometrics`) to
     add a new suffix to it, or a new name to propose a new modality. The suffix
     is always required.
   - Sheet `Types` (optional): a short vocabulary of the measurements your
     modality knows (for example CRP, glucose, cortisol), each with a
     description. A column can then carry a `Type` from this list or `other`, so
     the same measurement gets the same name across studies even when column
     names differ. New types are added later through an upstream pull request.
   - Sheet `Entities` (optional, new modalities only): suggested values for the
     `task` or `acq` filename parts, e.g. `acq | fasting`. Not allowed when you
     add a suffix to an existing modality.
   - Sheet `Columns`: the columns of your **sample file**, as an example (two or
     three are enough; every study defines its own columns in its own sidecar),
     with `ID`, `Description`, `Units`, `DataType` (string, integer or float;
     guessed if empty), `Scale` (optional drop-down: categorical, continuous or
     boolean; leave empty for identifiers, times and free text), `Type`
     (optional, from the `Types` sheet or `other`), `Min`, `Max`,
     `AllowedValues` (separated by `;`). A continuous column must be a number
     without `AllowedValues`, a categorical column needs its categories in
     `AllowedValues`, a boolean column needs exactly two (for example `yes; no`).
2. A small **synthetic** sample data file in the same format as your real data:
   at most 50 rows and 1 MB. Its header must match the `Columns` sheet. Never
   use real participant data.

## Existing modality or new one?

- **Name is an existing PRISM modality** (for example `biometrics`): you add a
  new filename ending (suffix) such as `bloodpanel` to it. The modality keeps
  its folder, schema and naming rules; no new schema file is written, and
  `Entities` suggestions are not allowed.
- **Name is new**: you propose a new modality (its folder) with its schema.
  `examples/modality_proposal/bloodwork.yml` is the new-modality example and
  `examples/modality_proposal/bloodpanel.yml` the suffix example.

BIDS-owned names cannot be extended here; propose those to BIDS upstream.

## Filenames

A new modality uses one fixed filename pattern:

    sub-<label>[_ses-<label>][_task-<label>][_acq-<label>][_run-<index>]_<suffix>.<extension>

`task` is optional. Any other entity in a filename is an error for a new
modality. Maintainers can refine the allowed parts per modality later.

## Choosing a name and suffix

Both must be lowercase letters and digits, starting with a letter, and must
not already be used by PRISM or BIDS. `blood` for example is a BIDS suffix
(blood radioactivity in PET). The check tells you what a taken name means.

## Submit it

**On GitHub:** use the Propose page in Studio, or open the
[Propose a new kind of data](https://github.com/MRI-Lab-Graz/prism-specification/issues/new?template=propose-new-kind-of-data.yml)
form in prism-specification. A maintainer takes it from there.

**From the command line:**

    python prism_tools.py modality propose my_proposal.xlsx --sample my_sample.tsv --check
    python prism_tools.py modality propose my_proposal.xlsx --sample my_sample.tsv --out my_modality

`--check` only validates. The second command writes the schema (new modalities
only), an example sidecar, a small dataset to test with, generated docs
(`docs/<name>.md` and `docs/snippets.md`, or `docs/<name>-<suffix>.md` when adding
a suffix) and `REGISTRATION.md`. YAML or JSON can
be used instead of the workbook (see `examples/modality_proposal/`).

## What happens next

A maintainer follows `REGISTRATION.md` (add the schema, the entities entry and
`specs/<name>.md` and the `specs/entities.md` row in prism-specification, tag a
release, run `python scripts/sync_specification.py --tag <tag>` in Studio, add
the docs card and toctree entry and run the checks including `modality-docs`) and reviews units, ranges and the
sample. After the merge the modality is available in the next PRISM release.
While the pull request only adds files under
`proposals/`, CI runs a reduced set (repo checks plus
`tests/test_modality_proposal_fixtures.py`) and skips the docs build and the
cross-platform tests. The fixture test stays red until the modality is
registered; the maintainer's registration push touches other files and runs the
full CI. The `modality-docs` check fails CI when a registered modality has no spec
page, toctree entry, card, `entities` table row or suffix mention.

## For maintainers

- Do not open a contributor's original `.xlsx` in desktop Excel (formulas or
  external links); review the generated JSON instead.
- Registration happens in the prism-specification repository (schema, entities
  entry, `specs/<name>.md`), then a Studio sync (the generated `REGISTRATION.md`
  lists the steps).
