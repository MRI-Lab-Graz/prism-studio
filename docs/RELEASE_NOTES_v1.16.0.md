---
orphan: true
---

# PRISM Studio v1.16.0 - Native Windows/Linux App Window and Server Hardening

PRISM Studio 1.16.0 gives packaged builds a native-feeling window on every
platform and closes out a round of localhost-server hardening surfaced by a
full repo security assessment.

## Highlights

- Packaged builds on Windows and Linux now open in a Chromium app-mode
  window (borderless, tab-less) instead of relying on pywebview's native
  backends, which do not survive PyInstaller freezing reliably on those
  platforms. macOS keeps its native pywebview/Cocoa window.
- The local server no longer trusts a hardcoded session secret, validates
  the Host header to defeat DNS-rebinding attacks, and keeps
  filesystem-browsing endpoints loopback-only even when `--public` is used
  to share the UI on a LAN.
- CI now runs lint/ruff/mypy checks on every push and pull request instead
  of only on manual dispatch.

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
