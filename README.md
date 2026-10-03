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

PRISM pairs every research data file with a JSON sidecar that explains it —
item wordings, response options, units, scoring — organized by subject,
session, and modality. Modalities, file-naming rules, and sidecar contracts
are JSON schemas, so the model extends to new instruments without code
changes, while staying compatible with standard BIDS tooling. PRISM currently
ships modalities and templates for psychological research (surveys,
biometrics). **PRISM Studio** is the local web and CLI tool that applies the
model to validation, conversion, and dataset management.

Full documentation, including a complete install and usage guide, is on
[ReadTheDocs](https://prism-studio.readthedocs.io). This README covers the
essentials to get running.

## Core Features

- Dataset validation and conversion
- PRISM Studio web interface, plus CLI workflows for terminal users
- Survey and biometrics metadata support
- Local-first operation (data stays on your machine; the only exception is
  optional, off-by-default environment enrichment, which sends coordinates
  and dates — never participant data — to a public weather service)

## Feature Scope

| Tier | Meaning | Examples |
|------|---------|----------|
| **Core loop** | The primary supported workflow; breaking changes here get release notes and migration guidance. | Survey conversion, dataset validation, DataLad-tracked provenance for mutations and recipe scoring, entity/filename rules ([`entities.schema.json`](docs/specs/entities.md)) |
| **Supported** | Deliberately-scoped bridges and integrations; stable, but intentionally narrower than the core loop. | BIDS `phenotype/` export/import bridge (lossy by design — see [ROADMAP.md](ROADMAP.md) Phase 1), recipe/derivative scoring |
| **Experimental** | Works, but has known rough edges or limited validation; use with care and report issues. | The Type-7 multiplexed decoder in the Varioport physio converter (flagged "QC required" in code) |

See [ROADMAP.md](ROADMAP.md) for the reasoning behind each scope decision.

The [Austrian NeuroCloud (ANC)](https://anc.plus.ac.at/) (CoreTrustSeal-certified)
officially accepts PRISM-formatted datasets alongside plain BIDS — see the
[data format requirements](https://handbook.anc.plus.ac.at/terms/data_format_requirements/).

## Installation

Python 3.10, 3.11, or 3.12 is required for source installation (3.9 and older
lack required features; 3.13+ has no wheels yet for some pinned scientific
dependencies). `install.sh` checks this automatically and, if your default
`python3` is outside that range, uses `uv` to find or install a compatible
version for you — no manual Python install needed.

### Pre-built binaries (recommended for most users)

Download the latest release for your platform from the
[Releases page](https://github.com/MRI-Lab-Graz/prism-studio/releases).

| Platform | Binary |
|----------|--------|
| macOS (Apple Silicon) | `prism-studio-macOS-AppleSilicon.zip` |
| Windows | `prism-studio-Windows.zip` |
| Linux | `prism-studio-Linux.zip` |

The binaries are not code-signed yet, so your OS may warn on first launch. Check that a
download is the one our build produced:

```bash
shasum -a 256 -c SHA256SUMS --ignore-missing      # Linux/macOS (Windows: Get-FileHash)
gh attestation verify prism-studio-Linux.zip --repo MRI-Lab-Graz/prism-studio
```

macOS: if Gatekeeper blocks the first launch, run `Prism Studio Installer.app`
from the extracted folder (fallback: `Open Prism Studio.command`).

### From source

```bash
bash install.sh          # macOS/Linux
install.cmd               # Windows — double-click, or run from any shell
```

Both create a virtual environment, install dependencies, and add a
**PRISM Studio** desktop shortcut. See the
[installation guide](https://prism-studio.readthedocs.io) for Windows
execution-policy notes and other platform-specific details.

## Quick Usage

After setup, activate the virtual environment (`source .venv/bin/activate`)
and run:

```bash
python prism-studio.py                    # Studio web app -> http://127.0.0.1:5001
python prism-validator /path/to/dataset   # Validator (CLI)
python prism_tools.py --help              # Other tools (CLI)
```

**Use a Chromium-based browser** (Chrome, Edge, Brave) for Studio — Safari can
be noticeably slower for local apps like this, especially with iCloud Private
Relay enabled.

A slim Docker image with just the validation engine is also published on
every release (`ghcr.io/mri-lab-graz/prism-validator`), with a matching
GitHub Action — see the [documentation](https://prism-studio.readthedocs.io)
for both.

## Documentation

Full documentation is on [ReadTheDocs](https://prism-studio.readthedocs.io).

## Report an Issue

Use the `Issues` tab to report bugs or request features:
`https://github.com/MRI-Lab-Graz/prism-studio/issues`

Include these details so we can reproduce quickly:
- Your OS and Python version
- The exact command you ran
- The full error message or screenshot
- A small dataset example (if possible)

## Citation

If you use PRISM, please cite it — see `CITATION.cff` for metadata, or use the
DOI directly: [10.5281/zenodo.22809100](https://doi.org/10.5281/zenodo.22809100)
(always resolves to the latest release). A companion paper has been submitted
to JOSS; see [`paper/paper.md`](paper/paper.md) in the meantime.

## License

See `LICENSE` (AGPL-3.0) for the software.

**The bundled instrument library is content, not code, and AGPL-3.0 does not
apply to it.** Survey templates under `official/library/survey/` carry their
own per-instrument terms in each template's `Study.License` field. See
[`official/library/NOTICE.md`](official/library/NOTICE.md) for provenance,
citation requirements, and what you must check before using an instrument.
