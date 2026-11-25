---
orphan: true
---

# PRISM Studio v1.26.2

## Before you update

- **Sending, syncing and getting data moved to [Worldline Desktop](https://worldline-desktop.readthedocs.io/).** PRISM no longer has `publish` or the `datalad sync | update | put-on-server | open-from-server | get-data` commands and buttons. Enable DataLad and Save stay. Scripts that call the removed commands will stop working.
- If you installed the old pre-push hook, run `prism_tools save-gate --install-hooks --project <root>`, or every push stays blocked.
- **Re-validate your projects.** The validator now reports a `participants.json` that says two opposite things about one code (`Levels` "1": "Male", `Annotations.Levels` "1": "Female"). Check those columns against your codebook, also in exports made from them.
- **Converted DASS-21 or other surveys with a per-language licence?** The sidecar was broken; convert that data again.

## Highlights

- **Recipe Builder:** formula scores and Best of N, with help, worked examples and a check on example values.
- **Conversions keep your `dataset_description.json`** instead of replacing it with placeholder values.
- **IDs:** biometrics measures have shared IDs, survey IDs can be deprecated, and two new commands report which IDs link to outside vocabularies (`terms coverage`) and export those links (`terms export-links`).
- **Your own surveys:** a project can recognise them by the wording of their items, without storing the item text.

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
