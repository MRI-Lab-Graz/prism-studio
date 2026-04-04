---
orphan: true
---

# PRISM Studio v1.14.0 - Wide-to-Long Conversion and Release Delivery Improvements

This release adds a new wide-to-long conversion workflow, improves packaged app distribution on macOS, and tightens release visibility and launch handling across the application.

## Highlights

- Added CLI-backed wide-to-long conversion with exact session indicator matching.
- Improved macOS first-launch experience with bundled installer helpers and clearer distribution flow.
- Added latest GitHub release detection in the UI and strengthened release packaging automation.

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