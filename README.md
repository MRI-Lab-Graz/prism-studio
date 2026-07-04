<p align="center">
	<img src="docs/img/prism_logo.png" alt="PRISM Logo" width="560">
</p>

<h1 align="center">PRISM Studio</h1>

<p align="center"><strong>Psychological Research Information System Model</strong></p>

<p align="center">
	<img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python 3.10+">
	<img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey" alt="Platform">
	<img src="https://img.shields.io/badge/BIDS-compatible-green" alt="BIDS compatible">
</p>

PRISM Studio is a comprehensive tool for managing psychological research datasets built on the PRISM framework.

PRISM (Psychological Research Information System Model) extends BIDS for modalities such as surveys and biometrics while staying compatible with standard BIDS apps. PRISM Studio applies that model in practical web and CLI workflows for validation, conversion, and dataset management.

## Core Features

- Dataset validation and conversion
- PRISM Studio web interface for interactive workflows
- CLI workflows for terminal users
- Survey and biometrics metadata support
- Local-first operation (data stays on your machine)

## Pre-built Binaries

Download the latest release from the [Releases page](https://github.com/MRI-Lab-Graz/prism-studio/releases).

| Platform | Binary | Notes |
|----------|--------|-------|
| macOS | `prism-studio-macOS-AppleSilicon.zip` | Apple Silicon (M1/M2/M3/M4) |
| macOS | `prism-studio-macOS-AppleIntel.zip` | Intel Macs |
| Windows | `prism-studio-Windows.zip` | x64 |
| Linux | `prism-studio-Linux.zip` | x64 |

macOS first launch: if Gatekeeper blocks the app, run `Prism Studio Installer.app` from the extracted release folder (fallback: `Open Prism Studio.command`).

## Installation

### Prerequisite

- Python 3.10 or newer is required for source installation (Python 3.9 is not supported).

### Using Pre-built Binaries (Recommended)

Download the latest release for your platform from the [Releases page](https://github.com/MRI-Lab-Graz/prism-studio/releases).

### From Source

One-time setup from repository root.

macOS/Linux:

```bash
bash setup.sh
```

Windows (PowerShell):

```powershell
.\setup.ps1
```

For detailed installation instructions, see the [documentation](https://prism-studio.readthedocs.io).

## Quick Usage

### Run via RTK (recommended)

After setup and virtual environment activation, use the `rtk` command for common workflows:

```bash
rtk studio
rtk validator /path/to/dataset --bids
rtk tools --help
rtk test -q
rtk coverage
rtk codecov upload-process
rtk git status
```

### Run PRISM Studio (Web)

```bash
python prism-studio.py
```

Open `http://127.0.0.1:5001` if it does not open automatically.

**For best performance, use a Chromium-based browser** (Chrome, Edge, Brave, etc.).
Safari can be significantly slower for local apps like PRISM Studio, especially
with iCloud Private Relay or "Hide IP address from trackers" enabled - turn
those off for this site, or switch browsers, if pages feel slow to load.

Pre-built binaries open PRISM Studio in its own native app window by default
(via `pywebview`) instead of a browser tab. Pass `--browser` to open it in
your default browser instead, `--window` to force the native window when
running from source, or `--no-browser` to skip auto-opening either.

### Run PRISM Validator (CLI)

```bash
python prism-validator /path/to/dataset
```

### Run PRISM Validator (Docker)

A slim, standalone validator image (just the CLI validation engine - no Flask, pandas, or
datalad) is published automatically to GHCR on every release:

```bash
docker pull ghcr.io/mri-lab-graz/prism-validator:latest
docker run --rm -v "$(pwd)":/data:ro ghcr.io/mri-lab-graz/prism-validator:latest /data
```

Or build it locally from this repo:

```bash
docker build -t prism-validator .
docker run --rm -v "$(pwd)":/data:ro prism-validator /data
```

For CI, add `--json` or `--format junit|sarif|markdown|csv` for machine-readable output
(printed to stdout by default - exit code is `0` when the dataset is valid, `1` otherwise).
Avoid the `-o FILE` flag with a bind-mounted dataset: the container writes as `root`, so any
file it creates inside the mount ends up `root`-owned on the host. Redirect from your shell
instead, e.g. `docker run ... --format junit > report.xml`.

### Run PRISM Tools (CLI)

```bash
python prism_tools.py --help
```

## Documentation

Comprehensive documentation is available on [ReadTheDocs](https://prism-studio.readthedocs.io).

## Report an Issue

Use the `Issues` tab to report bugs or request features:
`https://github.com/MRI-Lab-Graz/prism-studio/issues`

Include these details so we can reproduce quickly:
- Your OS and Python version
- The exact command you ran
- The full error message or screenshot
- A small dataset example (if possible)

## Citation

See `CITATION.cff` for citation metadata.

## License

See `LICENSE`.
