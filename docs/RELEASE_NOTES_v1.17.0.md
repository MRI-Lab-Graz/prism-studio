---
orphan: true
---

# PRISM Studio v1.17.0 - DataLad Reliability Hardening, BIDS Phenotype Bridge, Declarative Entity Rules

This release is anchored by a production incident: registering nested DataLad
subdatasets on a large (150-subject, 340GB) real-world dataset surfaced a
chain of DataLad/git-annex reliability bugs, all fixed here along with
proactive health checks so the same failure mode is caught early next time.
Also included: a BIDS `phenotype/` compatibility bridge, a declarative
entity/filename rules system, and recipe provenance tracking.

## Highlights

- **DataLad reliability**: fixed `.git/index.lock` collisions between
  concurrent operations, timeout-orphaned locks on long-running mutations,
  an unlocked-annex backlog that silently slows every git operation on a
  repo, and a silent git scoped-commit failure on git 2.54.0 that could make
  nested-subdataset registration appear to "restart from subject 1" forever.
  Proactive health checks now flag stale locks and unlocked-annex backlogs
  before they cause a mutation to fail partway through, and both `datalad
  push` and mutation-save failures are independently re-verified rather than
  trusted at face value.
- **BIDS `phenotype/` compatibility bridge**: opt-in export aggregates
  `survey/` data into a vanilla BIDS `phenotype/` directory; import fires
  automatically when initializing a project from a BIDS dataset that already
  has one.
- **Declarative entity/filename rules**: validator, rewriter, fix hints, and
  filename construction across survey/biometrics/physio now derive from a
  single schema instead of independently hardcoded copies.
- **Recipe provenance**: every recipe run gets a provenance sidecar with
  sha256-hashed input files, and `dataset_description.json` carries the real
  PRISM version.
- **Remote folder browsing** and **plain (non-RIA) DataLad sibling support**
  for the DataLad/rsync push-server destination fields.

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
