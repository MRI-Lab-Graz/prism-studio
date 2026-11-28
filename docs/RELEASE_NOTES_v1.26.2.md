---
orphan: true
---

# PRISM Studio v1.26.2

## Before you update

- **Sending, syncing and getting data moved to [Worldline Desktop](https://worldline-desktop.readthedocs.io/).** PRISM no longer has `publish` or the `datalad sync | update | put-on-server | open-from-server | get-data` commands and buttons. Enable DataLad and Save stay. Scripts that call the removed commands will stop working.
- If you installed the old pre-push hook, run `prism_tools save-gate --install-hooks --project <root>`, or every push stays blocked.
- **Re-validate your projects.** The validator now reports a `participants.json` that says two opposite things about one code (`Levels` "1": "Male", `Annotations.Levels` "1": "Female"). Check those columns against your codebook, also in exports made from them.
- **Converted DASS-21 or other surveys with a per-language licence?** The sidecar was broken; convert that data again.
- **Check templates imported from an Excel/CSV codebook.** Answer labels containing commas were cut off ("meistens, die ganze Zeit" became "meistens", "0,5 Jahre" became "0"), so different answers could read the same. The data values are not affected; compare the labels with your codebook.
- **Check `participants.json` if you annotated education.** The term codes Studio offered for education levels were gene codes. Some other codes (handedness, sex "Other", study group, autism) were wrong, missing or retired too. Validation now warns about each; remove the `TermURL`.
- **Converted LimeSurvey data using the `id` column as participant ID?** `id` numbers the responses and restarts in every survey, so timepoints could be filed under the wrong people. It is no longer accepted: check those conversions and convert again with the right column or `--id-map`.

## Highlights

- **Recipe Builder:** formula scores and Best of N, with help, worked examples and a check on example values.
- **Conversions keep your `dataset_description.json`** instead of replacing it with placeholder values.
- **IDs:** biometrics measures have shared IDs, survey IDs can be deprecated, and two new commands report which IDs link to outside vocabularies (`terms coverage`) and export those links (`terms export-links`).
- **Your own surveys:** a project can recognise them by the wording of their items, without storing the item text.

- **Much faster validation** of projects with many files (a 121-subject project: 19 s to 1.4 s for the PRISM rules, same messages).
- **Participant columns have shared term IDs** (`"Term"` in `participants.json`); the validator gives notices, never errors.
- **The save check works with `pip install prism-validator` alone.** Hooks written earlier still ask for `prism_tools`: run `prism_tools save-gate --install-hooks --project <root>` once.
- **Recipe formulas can use participant variables** from `participants.tsv`.
- **Imports tell you what they lose:** codebook imports warn about ignored text, repeated codes and equal answer labels.
- **Raw LimeSurvey response exports** (`.xlsx`/`.csv`) are read completely.

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
