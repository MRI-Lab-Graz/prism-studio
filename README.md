<p align="center">
	<img src="docs/img/prism_logo.png" alt="PRISM Logo" width="560">
</p>

<h1 align="center">PRISM Studio</h1>

<p align="center"><strong>Principled Research Information & Sidecar Model</strong></p>

<p align="center">
	<img src="https://img.shields.io/badge/python-3.10--3.12-blue" alt="Python 3.10-3.12">
	<img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey" alt="Platform">
	<img src="https://img.shields.io/badge/BIDS-compatible-green" alt="BIDS compatible">
	<a href="https://doi.org/10.5281/zenodo.22809100"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.22809100.svg" alt="DOI"></a>
</p>

PRISM Studio is a local tool for describing, validating, and managing research datasets built on the PRISM model.

PRISM (Principled Research Information & Sidecar Model) pairs every data file with a JSON sidecar that explains it, organized by subject, session, and modality. Modalities, file-naming rules, and sidecar contracts are JSON schemas, so the model extends to new instruments and new fields without code changes. PRISM stays compatible with standard BIDS apps and currently ships modalities and templates for psychological research, such as surveys and biometrics. PRISM Studio applies the model in practical web and CLI workflows for validation, conversion, and dataset management.

## Core Features

- Dataset validation and conversion
- PRISM Studio web interface for interactive workflows
- CLI workflows for terminal users
- Survey and biometrics metadata support
- Local-first operation (data stays on your machine; the only exception is
  optional, off-by-default environment enrichment, which sends coordinates
  and dates — never participant data — to a public weather service)

## Feature Scope

To help third parties know what to rely on, PRISM's features fall into three
tiers:

| Tier | Meaning | Examples |
|------|---------|----------|
| **Core loop** | The primary supported workflow; breaking changes here get release notes and migration guidance. | Survey conversion, dataset validation, DataLad-tracked provenance for mutations and recipe scoring, entity/filename rules ([`entities.schema.json`](docs/specs/entities.md)) |
| **Supported** | Deliberately-scoped bridges and integrations; stable, but intentionally narrower than the core loop. | BIDS `phenotype/` export/import bridge (lossy by design — see [ROADMAP.md](ROADMAP.md) Phase 1), recipe/derivative scoring |
| **Experimental** | Works, but has known rough edges or limited validation; use with care and report issues. | The Type-7 multiplexed decoder in the Varioport physio converter (flagged "QC required" in code) |

See [ROADMAP.md](ROADMAP.md) for the reasoning behind each scope decision.

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

- Python 3.10, 3.11 or 3.12 is required for source installation. 3.9 and older lack
  required features; 3.13+ has no wheels yet for some pinned dependencies, so
  installation falls back to a source build that needs a C compiler.

### Using Pre-built Binaries (Recommended)

Download the latest release for your platform from the [Releases page](https://github.com/MRI-Lab-Graz/prism-studio/releases).

### From Source

One-time setup from repository root.

macOS/Linux:

```bash
bash setup.sh
```

Windows: double-click **`setup.cmd`**, or run it from any shell:

```
setup.cmd
```

It unblocks the downloaded files, runs `setup.ps1`, then activates the
environment and starts PRISM Studio. Arguments are passed through
(`setup.cmd -Build -Dev`). It also puts a **PRISM Studio** shortcut on the
Desktop, with the app icon — double-click that to start PRISM Studio from then
on. (The shortcut runs `start.cmd`, which you can also launch directly. To
recreate the shortcut later:
`powershell -ExecutionPolicy Bypass -File scripts\setup\create_desktop_shortcut.ps1`.
The shortcut uses `app\static\img\MRI_Lab_Logo.ico` — a real multi-size icon
file, unlike `app\static\prism2026.ico`, which is a PNG that Explorer
rejects with "contains no icons" despite the `.ico` extension.)

`setup.cmd` exists because Windows marks every file extracted from a
downloaded ZIP as "from the internet", and PowerShell's default `RemoteSigned`
policy then refuses to run `setup.ps1` (*"is not digitally signed" / "kann
nicht geladen werden"*). Batch files are exempt from that policy, so
`setup.cmd` works where calling `setup.ps1` directly does not. To run
`setup.ps1` yourself instead, clear the mark first:

```powershell
Get-ChildItem -Recurse | Unblock-File
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

Pre-built binaries open PRISM Studio in its own app window by default instead
of a browser tab (a native WebKit window on macOS; a tab-less Chromium/Edge
"app mode" window on Windows and Linux). Pass `--browser` to open it in your
default browser instead, `--window` to force the app window when running from
source, or `--no-browser` to skip auto-opening either. If no suitable window
backend is available, it falls back to opening your default browser.

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

For GitHub Actions, [`action.yml`](action.yml) wraps the same image as a one-step
Action (`uses: MRI-Lab-Graz/prism-studio@main`) — see
[`official/anc_templates/example-github-actions.yml`](official/anc_templates/example-github-actions.yml)
for a full workflow. For GitLab CI (which can't consume a GitHub Action), see
[`official/anc_templates/example-gitlab-ci.yml`](official/anc_templates/example-gitlab-ci.yml)
for the equivalent direct Docker invocation.

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

See `LICENSE` (AGPL-3.0) for the software.

**The bundled instrument library is content, not code, and AGPL-3.0 does not
apply to it.** Most survey templates under `official/library/survey/` derive
from the [PsyToolkit survey library](https://www.psytoolkit.org/survey-library/)
and carry their own per-instrument terms in each template's `Study.License`
field. See [`official/library/NOTICE.md`](official/library/NOTICE.md) for
provenance, citation requirements, and what you must check before using an
instrument.
