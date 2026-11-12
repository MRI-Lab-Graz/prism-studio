---
orphan: true
---

# PRISM Studio v1.25.1

## Highlights

- **Survey import keeps your `participants.tsv`.** Saving a conversion into a project no longer overwrites the project's
  participants files; only new subjects are added.
- **The session review table opens even when a relabel gives one participant the same session twice**; the clash is a warning there and the conversion still refuses it.
- **Answer code numbers can be changed later** (ADS0 → 0): in the template editor or with `survey answer-codes --set`.

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
