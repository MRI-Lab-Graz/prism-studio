# Converter — Eyetracking

Batch-converts SR Research EyeLink eyetracking recordings into BIDS-style eyetracking
outputs. Eyetracking is a **BIDS passthrough modality** in PRISM — there is no
PRISM-specific content processing, column renaming, or sidecar-field normalization
applied to your data. This screen only renames files into BIDS naming and generates a
minimal sidecar; it does not touch the file's internal content.

## Supported input

- `.edf` — raw EyeLink recordings. Sampling frequency and duration are read from the
  EDF header (via `pyedflib`, when available) and written into the sidecar.
- `.tsv` / `.tsv.gz` — pre-processed trial-summary tables (e.g. exported from EyeLink
  Data Viewer). These are copied through with a plain sidecar; there's no EDF header
  to read, so sampling-frequency/duration fields are omitted rather than guessed.

Both input kinds keep their own extension on output — a `.tsv` file never gets
written out disguised as a `.edf` file.

## Required naming

```text
sub-<label>[_ses-<label>]_task-<label>_eyetracking.[edf|tsv|tsv.gz]
```

Session is optional. Example: `sub-003_ses-1_task-reading_eyetracking.edf`.

## Step 1 — Select files

**Select Eyetracking Files** accepts multiple `.edf`, `.tsv`, `.tsv.gz` files at once.

## Step 2 — Preview and convert

**Preview (Dry-Run)** shows what would be created without writing anything.
**Convert** runs the real batch conversion, with a progress bar, a **Cancel Running
Conversion** option, and a collapsible Conversion Log.

## Output

```text
sub-<label>/[ses-<label>/]eyetracking/sub-<label>_[ses-<label>_]<task>_eyetrack.<ext>
sub-<label>/[ses-<label>/]eyetracking/sub-<label>_[ses-<label>_]<task>_eyetrack.json
```

Note the output suffix is `eyetrack` (not `eyetracking`) — that's the BIDS-standard
suffix, even though the *input* naming convention above uses `_eyetracking`.

## What's next

- [Converter — Physio](converter_physio.md)
- [Validator](validator.md)
