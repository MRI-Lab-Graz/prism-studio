---
orphan: true
---

# PRISM Studio v1.18.1 - Windows First-Launch Fix, Linux/macOS Packaging Fix

This release fixes two packaging bugs that only show up in the prebuilt
releases, not in source installs: a Windows first-launch race that could show
a connection-refused page, and a Linux/macOS packaging regression that broke
the app entirely.

## Highlights

- **Windows first launch could show "this site can't be reached"**: the
  packaged app's window opened before the local server finished starting.
  Windows Defender's real-time scan and SmartScreen reputation check on a
  brand-new, freshly installed exe can take long enough on first run to
  outlast the previous ~10 second wait. The wait is now up to 45 seconds;
  later launches (once Defender's verdict is cached) were never affected.
- **Packaged Linux/macOS builds could fail to load any page**: a recent
  PyInstaller packaging change dropped a compiled stdlib module
  (`cmath`) that numpy/pandas need at runtime, breaking several parts of the
  interface in frozen builds. Windows builds were unaffected. Fixed by
  declaring the dependency explicitly.

See `CHANGELOG.md` for the full list of changes since v1.18.0.

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
`docs/INSTALLATION_SECURITY.md`) and is unrelated to the connection-refused
issue fixed in this release.

## Notes

- PRISM extends BIDS and remains compatible with BIDS apps.
- This build remains unsigned; see `docs/INSTALLATION_SECURITY.md`.
- See `CHANGELOG.md` for full technical details.
