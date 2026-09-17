---
orphan: true
---

# PRISM Studio v1.19.0 - JOSS Submission Readiness

This release clears the release-quality and manuscript issues found while
preparing the PRISM paper for submission to the Journal of Open Source
Software (JOSS): a red CI (two stale tests, 27 mypy errors), a paper over
JOSS's word limit with stale version references and orphaned figure assets,
and Zenodo archival for a citable DOI.

## Highlights

- **CI is green again**: two stale test assertions in
  `test_tools_file_browser_handlers.py` and all 27 mypy errors across 12
  files are fixed. The paper's claim that CI runs mypy is now actually true.
- **Paper trimmed under JOSS's 1750-word limit** (from ~1831 to ~1740
  words), with a new figure comparing PRISM's native, acquisition-scoped
  survey layout to the optional BIDS `phenotype/` compatibility export.
  Three other figure assets with no corresponding prose were removed.
- **Zenodo archival enabled**: this release is the first to mint a citable
  DOI via Zenodo's GitHub integration. `CITATION.cff` now lists all three
  paper authors (previously missing two) and stays in sync with the DOI.

See `CHANGELOG.md` for the full list of changes since v1.18.1.

## Downloads

- Windows: `prism-studio-Windows.zip`
- macOS (Apple Silicon): `prism-studio-macOS-AppleSilicon.zip`
- macOS (Intel): `prism-studio-macOS-AppleIntel.zip`
- Linux: `prism-studio-Linux.zip`

## macOS First Launch

If macOS blocks the app on first launch, open the extracted release folder and double-click:

`Prism Studio Installer.app`

If App Translocation prevents auto-detection, the installer asks you to select `PrismStudio.app` once.

Fallback:

`Open Prism Studio.command`

This helper removes quarantine metadata from `PrismStudio.app` and starts the app.

If needed, Finder fallback:
1. Right-click `PrismStudio.app`
2. Click **Open**
3. Confirm **Open** in the dialog

Apple guide for "Open Anyway":
https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac

## Windows First Launch

Windows Defender SmartScreen shows a "Windows protected your PC" screen the
first time you run `PrismStudio.exe`. Click **More info**, then **Run
anyway**. This is expected for an unsigned build (see
`docs/INSTALLATION_SECURITY.md`).

## Notes

- PRISM extends BIDS and remains compatible with BIDS apps.
- This build remains unsigned; see `docs/INSTALLATION_SECURITY.md`.
- See `CHANGELOG.md` for full technical details.
