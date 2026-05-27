---
orphan: true
---

# PRISM Studio v1.15.3 - Frontend Hardening and Export Privacy Follow-Through

PRISM Studio 1.15.3 turns a broad hardening tranche into a release cut. The focus is stability: finish the frontend structural-assessment remediation work, tighten export privacy behavior, and raise confidence in release-readiness checks before the next official tag.

## Highlights

- Top-level frontend workflows now share a more consistent page shell and have focused regression coverage around wiring, polling, and state-ownership boundaries.
- Export privacy handling is stronger, with MRI sidecar scrubbing, `.nii.gz` header cleanup, and explicit coverage for defacing confirmation inheritance across global and project settings.
- Release confidence is higher thanks to synchronized version metadata checks, focused cross-platform validation, and fresh GitHub build verification across Windows, macOS, and Linux.

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

## Notes

- PRISM extends BIDS and remains compatible with BIDS apps.
- See `CHANGELOG.md` for the full technical change list.