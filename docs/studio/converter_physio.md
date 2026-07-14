# Converter — Physio

Batch-converts physiological recordings (Varioport `.raw`/`.vpd` devices) into
BIDS-style physio outputs. Under the hood this drives the same batch-conversion path
as the CLI's `prism_tools.py physio batch-convert` — not `convert physio` (a separate,
older single-file/sourcedata-folder path that this tab does not use).

## Required naming

```text
sub-<label>[_ses-<label>]_task-<label>.[raw|vpd]
```

## Step 1 — Select files or a folder

- **Select Physio Files** — pick individual `.raw`/`.vpd` files.
- **Or Select a Folder** — pick a whole folder, or click **Auto-detect** to look for
  `sourcedata/physio/` in your current project automatically.

## Step 2 — Advanced settings (optional)

A separate **Advanced** sub-tab exposes:

- **Device Type** — currently locked to Varioport (`.raw`/`.vpd`).
- **Base Sampling Rate Override** — defaults to 512 Hz.
- **Expected Channels** — informational readout (EKG, EDA, Marker), not configurable.
- **Generate per subject/session HTML report in `derivatives/physio`** — checked by
  default.

## Step 3 — Preview and convert

**Preview (Dry-Run)** and **Convert** buttons, both disabled until files/folder are
selected. A progress bar, **Cancel Running Conversion**, and a live Conversion Log
appear once running.

## What's next

- [Converter — Eyetracking](converter_eyetracking.md)
- [Validator](validator.md)
