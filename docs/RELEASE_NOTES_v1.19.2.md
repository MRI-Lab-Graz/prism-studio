---
orphan: true
---

# PRISM Studio v1.19.2

## Highlights

- **`prism-validator` works on real projects (issue #162).** The PyPI validator no longer crashes on a
  dataset with a `project.json`; `--format json` now carries a `valid` verdict like `--json`; `--bids`
  fails closed (new error `PRISM902`) when no BIDS validator can run, so a save gate cannot pass by
  accident; in `--json`/`--format` modes stdout is JSON only. The JSON shapes and exit codes
  (0 valid, 1 errors, 2 could not run) are documented in `docs/CLI_REFERENCE.md`.
- **CITATION.cff is checked in the standalone validator**, and an unquoted `date-released: 2026-01-01`
  is no longer reported as invalid.
- **Error counts are right in the JUnit, SARIF, markdown and CSV outputs** (errors were counted as info).
- **LimeSurvey import, one template per questionnaire.** Template Editor > Import Template Source lists the
  questionnaires found in a `.lss`/`.lsa`, lets you split by question group, by question or the whole
  survey, and loads one at a time with real items and the array instructions in the right place. The
  terminal shows every step. `survey import-limesurvey` offers the same choices on the command line.
- **Library match.** An imported questionnaire is compared by wording with the global and project template
  libraries; a one-to-one match can be used instead, keeping the library's item IDs (your survey's codes
  are stored as aliases). The global library is never written.
- **Import hint.** Fields LimeSurvey cannot contain are listed as "Not found in your file" instead of a
  red validation failure.

## Changed / Removed

- `survey import-limesurvey`: `--output` is now a directory and `--task` is gone (breaking for old scripts).
- The Survey Generator's "Individual questions" export (one template per single question) is removed.

See `CHANGELOG.md` for the full list of changes since v1.19.0.

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
