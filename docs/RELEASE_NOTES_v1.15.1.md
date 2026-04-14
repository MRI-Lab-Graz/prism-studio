---
orphan: true
---

# PRISM Studio v1.15.1 - Project Workflow Refinements and Release Pipeline Updates

This patch release improves project metadata workflows, strengthens import/template handling with PRISMMETA code mapping, and updates release pipeline conventions for more consistent packaged artifacts.

## Highlights

- Added runtime capabilities checks in project selection and packaged smoke probes, including pyreadstat support detection.
- Added PRISMMETA CodeMap integration for reversible LimeSurvey code sanitization and better template matching.
- Improved project save/validation behavior, accessibility feedback surfaces, and release artifact naming consistency.

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
