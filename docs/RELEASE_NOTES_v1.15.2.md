---
orphan: true
---

# PRISM Studio v1.15.2 - Workflow Safety, Project Context Hardening, and Platform Readiness

This release delivers a broad workflow-focused update across project management, conversion/export tooling, validation UX, and packaged-app reliability. The core goal is to reduce user-facing failure modes from stale state, stale assets, and mismatched project context while expanding key tooling capabilities.

## Feature Update

### Workflow and Project Safety

- Projects now preserve the active project context by default when opening the Projects page.
- Opening a project (directly or from recent projects) now routes into immediate project validation.
- Tool pages now provide clearer guidance when no active project is selected.
- Validation resume now checks target compatibility before auto-resume and clears stale incompatible state.

### Converter, Export, and Data Operations

- Added file deletion support with preview/filtering controls in file management workflows.
- Added template item deletion support in the template editor.
- Expanded project export with output-folder preferences, project-structure filtering controls, and defacing/MRI JSON scrub reporting.
- Expanded survey handling with structured survey modality support and stronger multi-version import paths.

### Validation and Interop

- Added modality-aware BIDS entity rewriting support with dedicated test coverage.
- Improved BIDS/PRISM validation mode isolation and result clarity.
- Strengthened modality and issue handling in reporting/validation paths (including beh-focused workflows).
- Improved metadata quality checks and issue normalization behavior.

### Platform and Release Hardening

- Expanded runtime capability checks used by packaged smoke/release flows.
- Added static asset versioning and no-store behavior to reduce stale frontend bundle issues after updates.
- Strengthened API fallback paths for packaged/file-mode reliability across multiple pages.
- Aligned local Windows build helper output guidance with PrismStudio executable naming.

## Downloads

- Windows: prism-studio-Windows.zip
- macOS (Apple Silicon): prism-studio-macOS-AppleSilicon.zip
- macOS (Intel): prism-studio-macOS-AppleIntel.zip
- Linux: prism-studio-Linux.zip

## macOS First Launch

If macOS blocks the app on first launch, open the extracted release folder and double-click:

Prism Studio Installer.app

If App Translocation prevents auto-detection, the installer asks you to select PrismStudio.app once.

Fallback:

Open Prism Studio.command

This helper removes quarantine metadata from PrismStudio.app and starts the app.

If needed, Finder fallback:

1. Right-click PrismStudio.app
2. Click Open
3. Confirm Open in the dialog

Apple guide for "Open Anyway":
https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac

## Notes

- PRISM extends BIDS and remains compatible with BIDS apps.
- See CHANGELOG.md for full technical details.
