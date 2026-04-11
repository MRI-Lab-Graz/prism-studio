---
orphan: true
---

# PRISM Studio v1.15.0 - Survey Versioning, Recipes, and Release Hardening

This release expands survey conversion workflows with version-aware handling, adds major recipe-builder capabilities, improves LimeSurvey tooling, and strengthens release reliability across packaged application builds.

## Highlights

- Added multi-version survey handling across project registration, conversion, preview, and template workflows.
- Expanded recipe tooling with coverage checks, anonymized exports, richer item metadata, and minimum-valid score support.
- Hardened packaged releases with smoke tests, endpoint probes, safer terminal relaunch behavior, and startup reliability fixes.

## Downloads

- Windows: `prism-studio_windows.zip`
- Windows Portable: `prism-windows-portable.zip`
- macOS (Apple Silicon): `prism-studio_apple-silicon.zip`
- macOS (Intel): `prism-studio_intel.zip`
- Linux: `prism-studio_linux.zip`

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