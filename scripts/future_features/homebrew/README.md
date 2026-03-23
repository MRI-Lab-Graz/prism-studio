# Homebrew Cask Distribution (Future Feature)

This folder contains the Homebrew cask formula and tooling for distributing PRISM Studio via Homebrew.

## What's Here

- **prism-studio.rb** — Cask formula for official Homebrew submission
- **update_cask_formula.py** — Script to inject SHA256 checksums from release artifacts
- **README.md** — This file

## When to Use This

This will be implemented when:
1. PRISM Studio repo is stable and ready for public distribution
2. Ready to submit to official [Homebrew/homebrew-cask](https://github.com/Homebrew/homebrew-cask) repository

## How It Works

1. **For maintainers**: When submitting to Homebrew, copy `prism-studio.rb` to a fork of `homebrew-cask`, run the checksum script with real artifact paths, and submit a pull request.

2. **For users** (once approved): Simply run:
   ```bash
   brew install --cask prism-studio
   ```

## Cask Features

- **Automatic quarantine removal** — macOS Gatekeeper quarantine metadata is removed on install
- **Dual architecture support** — Separate SHA256 for arm64 (Apple Silicon) and x86_64 (Intel)
- **Auto-detection** — Homebrew selects correct ZIP based on CPU architecture
- **Live version tracking** — Automatically detects new releases from GitHub

## Implementation Steps (When Ready)

1. Update `prism-studio.rb` with actual SHA256 checksums
2. Fork [Homebrew/homebrew-cask](https://github.com/Homebrew/homebrew-cask)
3. Add `Casks/prism-studio.rb` to the fork
4. Submit pull request following Homebrew guidelines
5. Address maintainer feedback (typically 1-2 weeks)
6. Once merged, PRISM Studio is available via `brew install --cask prism-studio`

## Notes

- No separate Homebrew tap repository needed—official Homebrew distribution only
- No account, license, or approval needed from Homebrew before submission
- The repository `homebrew-cask` is community-maintained; formula updates go through their process
- Users get automatic updates via `brew upgrade`

## References

- [Homebrew Adding Software Guide](https://docs.brew.sh/Adding-Software-to-Homebrew)
- [Acceptable Casks](https://docs.brew.sh/Acceptable-Casks)
- [Cask Cookbook](https://docs.brew.sh/Cask-Cookbook)
