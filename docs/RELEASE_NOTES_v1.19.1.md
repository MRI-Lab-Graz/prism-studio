---
orphan: true
---

# PRISM Studio v1.19.1

## Highlights

- **`prism-validator` on PyPI**: `pip install prism-validator` installs the
  command-line validator on its own (jsonschema, bids-validator, defusedxml;
  no Flask, pandas or DataLad). The Studio commands `wide-to-long` and
  `file-management` now live only in `prism_tools.py`.
- **Save gate**: in a DataLad project a change can be saved only if the dataset
  validates; without DataLad nothing changes.
- **Publish to the server** only when the dataset validates, with an audit log.
- **DataLad doctor**: `prism_tools.py datalad doctor|sync|finalize` checks the
  computer and server connection and pushes.
- **Installer fix**: `install.sh` works with uv-managed Python on macOS.

## Removed

- **Intel macOS build.** Homebrew no longer builds Intel macOS packages and
  GitHub is dropping Intel runners, so there is no Intel Mac download. Intel
  Macs can run PRISM Studio from source (`bash install.sh`).

See `CHANGELOG.md` for the full list of changes since v1.19.0.

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
