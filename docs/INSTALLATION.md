# Installation

Get PRISM Studio running. Most people only need the first section below.

## Prebuilt Release (Recommended)

Download the latest release, extract it, and start PRISM Studio from the extracted
folder — no Python or repository setup needed.

1. Open the [latest release page](https://github.com/MRI-Lab-Graz/prism-studio/releases/latest).
2. Pick your OS and download the matching ZIP:

  <details>
  <summary><strong>macOS</strong></summary>

  Choose your Mac chip and download the matching ZIP:
  - Apple Silicon (M1/M2/M3/M4): `prism-studio-macOS-AppleSilicon.zip`
  - Intel: `prism-studio-macOS-AppleIntel.zip`

  Not sure which Mac you have? Apple menu → **About This Mac** → check the chip:
  anything with "Apple M..." is Apple Silicon, "Intel" is Intel.
  </details>

  <details>
  <summary><strong>Windows</strong></summary>

  Download: `prism-studio-Windows.zip`
  </details>

  <details>
  <summary><strong>Linux</strong></summary>

  Download: `prism-studio-Linux.zip`
  </details>

3. Extract the ZIP and start PRISM Studio from the extracted folder.
   - **macOS first launch**: if the OS blocks the app, use
     `Prism Studio Installer.app` or `Open Prism Studio.command` from the extracted
     folder, or right-click `PrismStudio.app` → Open once.
4. Confirm it worked: the interface should open automatically. If not, go to
   `http://localhost:5001`.

## Source Install (Advanced)

Use this only if you need local code changes, development work, or CLI usage from
the source tree. Requires **Python 3.10+** (3.9 is not supported).

Pick your OS:

<details>
<summary><strong>macOS / Linux</strong></summary>

```bash
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
./setup.sh
source .venv/bin/activate
python prism-studio.py
```
</details>

<details>
<summary><strong>Windows</strong></summary>

```powershell
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
.\setup.ps1
.venv\Scripts\activate
python prism-studio.py
```
</details>

Always activate the repo-local virtual environment first
(`source .venv/bin/activate` / `.venv\Scripts\activate`) — command-line tools run
with the wrong environment otherwise.

Once set up, the CLI tools are available directly:

```bash
prism-validator /path/to/dataset
python prism_tools.py recipes surveys --prism /path/to/dataset
```

`prism-validator` is a console script installed into `.venv/bin` — once the virtual
environment is active it runs directly (no `python` prefix), and is equivalent to
`python prism.py`. See [CLI Reference](CLI_REFERENCE.md) for the full command set.

**Updating**: `git pull` then re-run `./setup.sh` (or `setup.ps1` on Windows).

## Troubleshooting

- **App starts but no browser page appears** — open `http://localhost:5001` manually
  and check the terminal output for launch errors.
- **Python or package errors during source install** — use the prebuilt release
  unless you specifically need source; if you do need source, make sure `.venv` is
  activated before running any commands.

## What's Next

After installation: create or open a project, import data, validate the dataset, then
run scoring if needed.

- [Quick Start](QUICK_START.md)
- [Studio Guide](studio/index.md)
- [CLI Reference](CLI_REFERENCE.md)
