# Modality Proposal Workflow

This page walks through the whole path from "I measure something PRISM does not
know yet" to "it ships in the next release". The reference for the workbook
fields is [Proposing a New Modality](MODALITY_PROPOSALS.md).

PRISM is open and dynamic: anyone can propose a new modality or a new filename
ending (suffix) for an existing one. Propose it on the **Propose** page in
Studio (Specifications), or with the
[Propose a new kind of data](https://github.com/MRI-Lab-Graz/prism-specification/issues/new?template=propose-new-kind-of-data.yml)
form in prism-specification, and a maintainer registers it, so it can be part of
the next release. This page covers the maintainer's drafting tool,
`python prism_tools.py modality propose`, which turns a workbook into the files
a registration needs.

## How it works

```
 you                         maintainer
 ---                         ----------
 propose on the Propose page
 or the prism-specification  ─► drafts the files with
 form (description + sample)    `modality propose`, follows REGISTRATION.md,
                                reviews units / ranges, merges
                                       │
                                       ▼
                               modality in next release
```

Nothing is registered automatically; a person always decides.

## What you need

| You need | Details |
|---|---|
| The workbook | `official/create_new_modality/modality_proposal_template.xlsx` (Excel, LibreOffice or Numbers). YAML or JSON also work, see `examples/modality_proposal/`. |
| A sample data file | Same format as your real data, **synthetic**, at most 50 rows and 1 MB, header identical to the `Columns` sheet. |
| A GitHub account | Only to submit the form. The command-line route needs none. |
| A name and suffix | Lowercase letters and digits, starting with a letter, not already used by PRISM or BIDS (`blood` is taken by BIDS, for example). |

You do not need to install PRISM to submit through the prism-specification form.

## Step by step

### Existing modality or new one?

Decide this first, in the `Modality` sheet:

- **Existing PRISM modality name** (e.g. `biometrics`): you add a suffix (a new
  filename ending) to it. No new schema file; `Entities` is not allowed.
- **New name**: you propose a new modality (its folder). Its filenames follow
  the fixed pattern described in [Proposing a New Modality](MODALITY_PROPOSALS.md).

The suffix is always required.

### 1. Fill in the workbook

- **`Modality`**: `Name`, `Suffix`, `Extensions`, `Description`.
- **`Entities`** (optional, new modalities only): suggested `task` or `acq`
  values, e.g. `acq | fasting`.
- **`Types`** (optional): a short vocabulary, e.g. CRP, glucose, cortisol, so the
  same measurement gets the same name across studies.
- **`Columns`**: the columns of your sample file as an *example* (two or three
  are enough; each study defines its own columns in its own sidecar). Per
  column: `ID`, `Description`, `Units`, `DataType`, `Scale`, `Type`, `Min`,
  `Max`, `AllowedValues`.

Rules the check enforces: a *continuous* column is numeric and has no
`AllowedValues`; a *categorical* column lists its categories; a *boolean*
column has exactly two values (`yes; no`).

### 2. Make the sample file

A tab-separated file whose header matches the `Columns` sheet:

```
sample_id	draw_time	fasting	crp	glucose	cortisol
S001	08:15	yes	1.2	5.1	310
S002	10:40	no	0.8	6.0	280
```

Never use real participant data.

### 3. Check it locally (recommended)

```bash
python prism_tools.py modality propose my_proposal.xlsx --sample my_sample.tsv --check
```

Exit code 0 means the proposal is fine. On a problem you get the row and
column, for example:

```
ERROR: my_sample.tsv row 1 column 'crp': 'abc' is not a number
```

### 4. Submit it

**Via GitHub (no install):** open the
[Propose a new kind of data](https://github.com/MRI-Lab-Graz/prism-specification/issues/new?template=propose-new-kind-of-data.yml)
form in prism-specification, or use the Propose page in Studio, which fills it
in for you.

**From the command line:** maintainers draft the package from a workbook:

```bash
python prism_tools.py modality propose my_proposal.xlsx --sample my_sample.tsv --out my_modality
```

### 5. What you get

The output folder (and the pull request) contains:

| File | Purpose |
|---|---|
| `<name>.schema.json` | The PRISM schema for the modality (not written when you add a suffix to an existing modality) |
| `docs/<name>.md`, `docs/snippets.md` | Generated spec page and snippets (for a suffix: `docs/<name>-<suffix>.md`) |
| `example_sidecar.json` | A sidecar a study can start from |
| `fixture/` | A tiny dataset that must pass the validator |
| `proposal.xlsx`, `sample.tsv` | Your original inputs |
| `REGISTRATION.md` | The manual steps for the maintainer |

### 6. Maintainer steps

The maintainer follows `REGISTRATION.md`: in the **prism-specification**
repository add the schema, the `entities.schema.json` entry, `specs/<name>.md`
and the `specs/entities.md` row,
run its `python scripts/check_modalities.py` and tests, and tag a release; then
in Studio run `python scripts/sync_specification.py --tag <tag>`, add the
generated docs (toctree entry, card), run
`python tests/verify_repo.py --check modality-docs` (fails CI when a registered
modality lacks any of these) and validate `fixture/` with
`python prism.py <folder>/fixture`. CI runs the vendored
`scripts/specification/check_modalities.py` on Studio's copy. Units, ranges and the sample are reviewed by
hand. A pull request that only adds `proposals/` files gets a reduced CI run and
its fixture test stays red until the modality is registered; the registration
push runs the full CI.

A new modality is registered at version `1.0.0`. Later changes to it release a
new version: bump `version` in the stable schema and first copy the previous
file to the archive folder, both in prism-specification (its schema-versions CI
checks this, see [Schema versioning](SCHEMA_VERSIONING.md)); then tag a release
and run `python scripts/sync_specification.py --tag <tag>` in Studio.

### After the pull request

1. Check out the PR branch and follow `REGISTRATION.md`.
2. Push; the full CI runs.
3. Review by hand (units, ranges, no real participant data), then run
   `ponytail:ponytail-audit`.
4. Mark the PR ready and merge.
5. The modality ships in the next release; project pages pick it up from
   `entities.schema.json`.

## Maintainer notes

- Do not open a contributor's `.xlsx` in desktop Excel; review the generated
  JSON instead.

## Example

A complete example (venous blood drawn alongside MRI) lives in
`examples/modality_proposal/bloodwork.yml` with
`examples/modality_proposal/bloodwork_sample.tsv`:

```bash
python prism_tools.py modality propose examples/modality_proposal/bloodwork.yml \
    --sample examples/modality_proposal/bloodwork_sample.tsv --out bloodwork_out
```
