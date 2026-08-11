---
orphan: true
---

# PRISM Studio v1.17.1 - Windows/DataLad Hardening

This release hardens DataLad/git-annex behavior specifically for Windows
ahead of broader Windows rollout, closing gaps found during a pre-release
Windows readiness review.

## Highlights

- **git-annex adjusted-unlocked branches no longer misreported as a
  backlog**: Windows machines without symlink support (Developer Mode
  off) run git-annex on an "adjusted unlocked" branch as a supported
  fallback -- PRISM's health check previously misread this permanent
  state as a stalled-batch backlog and told users to run `git annex
  lock`, which fought the adjusted branch's normal operation.
- **Windows symlink/long-path status surfaced during project setup**:
  the DataLad preflight check now reports whether symlinks are
  supported and whether Windows long-path support is enabled, instead
  of failing silently deep into a later operation.
- **Dataset-fixer renames retry through transient antivirus file
  locks**, a common source of intermittent Windows-only rename failures.

See `CHANGELOG.md` for the full list of changes.

## Downloads

- Windows: `prism-studio-Windows.zip`
- macOS (Apple Silicon): `prism-studio-macOS-AppleSilicon.zip`
- macOS (Intel): `prism-studio-macOS-AppleIntel.zip`
- Linux: `prism-studio-Linux.zip`

## Notes

- PRISM extends BIDS and remains compatible with BIDS apps.
- See `CHANGELOG.md` for full technical details.
