---
orphan: true
---

# PRISM Studio v1.15.2 - Big Workflow Upgrade for Real-World Projects

PRISM Studio 1.15.2 is one of the largest quality and workflow updates in recent releases.
The focus is practical: make everyday project work smoother, safer, and more predictable,
especially when users switch projects, resume tasks, and move between tools.

## Why This Release Matters

- Less stale state and fewer hidden mismatches between UI context and backend project state.
- Fewer accidental re-runs caused by outdated resume/session payloads.
- Clearer project-open behavior with validation at the right step in the workflow.
- Stronger confidence for packaged app users across Windows, macOS, and Linux.

## What Is New

### Project Flow Reliability

- Opening Projects no longer silently clears the active project by default.
- Opening a project from explicit selection or recent links now triggers immediate validation routing.
- Tool pages now provide clearer guidance when no active project is set.
- Validation resume now checks target compatibility before auto-resuming and clears stale mismatches.

### Conversion, Templates, and File Operations

- File Management now supports deletion workflows with preview and filtering support.
- Template Editor now supports template item deletion directly in the workflow.
- Project export gained stronger controls for output folder preferences, project-structure filtering, and defacing/MRI JSON scrub reporting.
- Survey flows gained stronger structured-modality handling and improved multi-version behavior.

### Validation and BIDS/PRISM Interoperability

- Added modality-aware BIDS entity rewriting with dedicated coverage.
- Improved separation and clarity between BIDS and PRISM validation modes.
- Improved issue grouping and reporting clarity for modality-specific workflows, including beh paths.
- Tightened metadata quality checks and issue normalization behavior.

### Release and Platform Hardening

- Added static asset version tokens plus no-store behavior to reduce stale frontend bundles after updates.
- Expanded runtime capability checks used in packaged smoke and release flows.
- Strengthened API fallback handling across project-aware pages.
- Aligned Windows local build helper naming and run guidance with PrismStudio outputs.

## Quality Confidence

This release was validated with broad regression coverage, including runtime gate checks and Windows-focused suites, in addition to targeted workflow tests for project state handling and validation wiring.

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

## Thank You

Thanks for the detailed workflow feedback that drove this release.
PRISM remains a BIDS-compatible extension layer: it adds schema power without breaking compatibility with BIDS apps.

## Full Technical Details

See CHANGELOG.md for the complete technical change list.
