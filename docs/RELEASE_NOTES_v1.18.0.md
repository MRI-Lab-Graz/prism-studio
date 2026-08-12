---
orphan: true
---

# PRISM Studio v1.18.0 - Anonymization Security Fix, Study-Application Import, Repo Security Hardening

This release fixes a real security issue: deterministic anonymization
pseudonyms were derived from an unsalted hash of the plaintext participant
ID, making them brute-forceable by anyone with a published "anonymized"
dataset and this source code. Also included: study-application import for
MRI-Lab Graz's Pavlovia intake survey, a global default for export defacing
confirmation, and two new repo-wide security checks in CI.

## Highlights

- **Anonymization pseudonyms are no longer brute-forceable**: deterministic
  IDs are now seeded via HMAC-SHA256 with a per-mapping secret key,
  persisted alongside the (already sensitive, "KEEP THIS FILE SECURE")
  mapping file, instead of an unsalted hash of the plaintext ID.
- **MRI-Lab Graz study application import**, gated behind a Global
  Settings toggle (off by default): imports either the legacy Pavlovia
  field names or the newer internal format, prefilling the project
  metadata form. Also fixes author names being parsed in the wrong order
  and `studyDescription` writing to the wrong form field.
- **Global default for export defacing confirmation mode**: the "ask
  before defacing on export" behavior is now configurable once in Global
  Settings instead of only per-project.
- **Two new CI security checks**: `ruff-security` (AST-based, curated
  flake8-bandit rules) and full git-history secret scanning via
  `gitleaks git`.
- **`get_json_hash()` fix**: a broken conditional meant every JSON file
  hashed to the same value, silently breaking sidecar deduplication.
- **Windows fix**: the dataset fixer's rename action could fail with
  `FileExistsError` on Windows when correcting two independently broken
  filenames to the same target.

See `CHANGELOG.md` for the full list of changes.

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

## Notes

- PRISM extends BIDS and remains compatible with BIDS apps.
- See `CHANGELOG.md` for full technical details.
