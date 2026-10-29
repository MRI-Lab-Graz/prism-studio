---
orphan: true
---

# PRISM Studio v1.23.0

## Highlights

- **Specification lives in its own repository (breaking for environment).** Modality schemas, the term registry and
  the spec pages are vendored from prism-specification (v1.4.1). Environment format 1.1.0 is retired (environment
  2.0.0); the `eyetracking` modality is removed (eye tracking is BIDS physio).
- **Propose changes to the specification from Studio.** Local metrics and additions to a modality work in your
  project right away, and can be shared (`spec propose`, new kinds of data, grouped environment measurements,
  clearer forms).
- **Environment time windows.** `environment convert --window VAR:DURATION:STAT`, e.g. `temp_c:P3D:max`.
- **LimeSurvey and Pavlovia round trips are much more faithful.** Real LimeSurvey 6 archives (multilingual,
  checkbox/ranking/array questions, design options) import without silent losses, the export is a LimeSurvey 6
  file, and `survey prepare-pavlovia` turns Pavlovia responses into a table for `survey convert`.
- **One timepoint means `ses-1`.** In a `Timepoints: single` project all importers write `ses-1` and report the
  label they replaced.
- **Safer releases and installs.** A wrong `v*` tag no longer publishes anything; `install.sh` copes with an old
  `uv`; Linux gets an applications-menu launcher.

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
