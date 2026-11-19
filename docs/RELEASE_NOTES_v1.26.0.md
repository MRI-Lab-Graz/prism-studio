---
orphan: true
---

# PRISM Studio v1.26.0

## Highlights

- **Ontology-ready.** PRISM IDs are stable and resolvable (`https://w3id.org/prism-specification/...`). Links from an ID
  to an external vocabulary (SNOMED CT, LOINC, ChEBI and 26 others) live in a separate, checked `mappings/` layer, and
  PRISM never changes your data to carry meaning. DASS items and ten biosample terms are linked already. See
  `docs/ONTOLOGY_READY.md`.
- **Your lab can link its own terms.** `spec local add-term --link VOCABULARY=URL`, `terms propose --link` and the
  Propose-changes page store links in the project (`code/specification/mappings/`) and share them in proposals.
  `terms check-links` checks mapping files with the specification's own checker.
- **The `LOINC` sidecar field is gone** (biosample schema 1.1.3). The codes are links in `mappings/biosample/`.
- **BREAKING: `survey convert --alias` is removed.** Use the project item map (`survey item-map` or the Studio
  item-mapping dialog).
- **Session handling:** `sessions forget-import` lets you redo a wrong session numbering; clashing rows are red in the
  session review.
- **Backend-driven language and preview tools:** Add/Remove Language and Preview Questionnaire run the same backend
  functions as the CLI. Removing a language no longer empties the general header.
- **Documentation and examples use the demonstration questionnaire**, not third-party instruments.

Specification: prism-specification v1.5.23.

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
