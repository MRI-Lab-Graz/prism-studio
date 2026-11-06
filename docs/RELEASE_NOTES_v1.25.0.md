---
orphan: true
---

# PRISM Studio v1.25.0

## Highlights

- **DataLad has its own page** with one next step for the open project: open from server, enable, put on server, save, sync.
  *More* holds get latest, get data (with the export's filters) and the computer check. The same actions exist as
  `prism_tools.py datalad` commands (`status`, `open-from-server`, `put-on-server`, `get-data`, `update`, `sync`).
- **Saving and sending need a valid dataset**; "Save anyway" / `--allow-invalid` is an explicit, logged exception.
- **Your git name and email belong to you, not the project**, so they no longer travel with a push.
- **Removed:** RIA store support, `datalad config`, `datalad finalize`, the unvalidated sync, and the DataLad card on
  Settings and the panel on the Share page. The server is the project's plain `origin`.
- **WCAG enhanced view** (Settings, off by default); the project page can edit the saved session mapping; conversions
  list their subjects in `participants.tsv`; participants without a `sub-*` folder count as prescreening.

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
