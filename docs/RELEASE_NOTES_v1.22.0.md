---
orphan: true
---

# PRISM Studio v1.22.0

## Highlights

- **Methods section export.** `prism_tools methods generate` (and the Projects page) writes the Methods as
  Markdown, HTML, Word, TeX, or a BibTeX file of instrument references. The text covers acquisition parameters,
  session counts, scoring recipes and software versions; missing facts are warnings, never invented.
- **Re-importing a LimeSurvey export only brings in what is new.** "Skip surveys already in the project" skips
  responses already imported; the session review lists only new data. LimeSurvey imports no longer write
  `tool-limesurvey` files; the fingerprint now lives in `code/survey_imports.json`.
- **Physio is task-free (breaking).** The `events/` and `physiological/` folders are retired and reported as
  errors by the validator. Task-bound physio is converted to BIDS `_physio.tsv.gz` in `beh/`, `func/` or `eeg/`
  (`--destination`). Existing projects: delete the `*_physio.*` line from `.bidsignore` by hand.
- **Specifications page** renders the spec documents offline.

See `CHANGELOG.md` for the full list of changes.

## Downloads

- Windows: `prism-studio-Windows.zip`
- macOS (Apple Silicon): `prism-studio-macOS-AppleSilicon.zip`
- Linux: `prism-studio-Linux.zip`

## macOS First Launch

If macOS blocks the app on first launch, open the extracted release folder and double-click:

`Prism Studio Installer.app`

If App Translocation prevents auto-detection, the installer asks you to select `PrismStudio.app` once.

Fallback:

`Open Prism Studio.command`
