---
orphan: true
---

# PRISM Studio v1.26.1

## Highlights

- **The packaged app starts again.** The Converter page of the 1.26.0 desktop builds crashed because the biosample template and import looked for their schema in a folder the packaged app does not have; they now read it from the folder Studio loads its schemas from. The `prism-validator` wheel of 1.26.0 was not affected.

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
