# Installation

Get PRISM Studio running. Most people only need the first section below.

## Prebuilt Release (Recommended)

Download the latest release, extract it, and start PRISM Studio from the extracted
folder — no Python or repository setup needed.

1. Open the [latest release page](https://github.com/MRI-Lab-Graz/prism-studio/releases/latest).
2. Pick your OS and download the matching ZIP:

<div class="prism-os-grid">

<details class="prism-os-card">
<summary><span class="prism-os-icon"><svg viewBox="0 0 24 24"><path d="M16.7 12.4c0-2.7 2.2-4 2.3-4.1-1.3-1.9-3.3-2.1-4-2.2-1.7-.2-3.3 1-4.2 1-.9 0-2.2-1-3.6-1-1.9 0-3.6 1.1-4.5 2.7-1.9 3.3-.5 8.2 1.4 10.9.9 1.3 2 2.9 3.4 2.8 1.4-.1 1.9-.9 3.5-.9s2.1.9 3.5.9c1.5 0 2.4-1.4 3.3-2.7.6-.9 1-1.8 1.4-2.8-1.9-.7-2.5-2.6-2.5-2.6Z"/><path d="M13.9 4.1c.7-.9 1.2-2.1 1.1-3.3-1.1.1-2.3.7-3 1.6-.7.8-1.3 2.1-1.1 3.3 1.2.1 2.4-.6 3-1.6Z"/></svg></span>macOS</summary>

<div class="prism-os-body">

Choose your Mac chip and download the matching ZIP:
- Apple Silicon (M1/M2/M3/M4): `prism-studio-macOS-AppleSilicon.zip`
- Intel: `prism-studio-macOS-AppleIntel.zip`

Not sure which Mac you have? Apple menu → **About This Mac** → check the chip:
anything with "Apple M..." is Apple Silicon, "Intel" is Intel.

</div>
</details>

<details class="prism-os-card">
<summary><span class="prism-os-icon"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="8" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/><rect x="13" y="13" width="8" height="8" rx="1"/></svg></span>Windows</summary>

<div class="prism-os-body">

Download: `prism-studio-Windows.zip`

</div>
</details>

<details class="prism-os-card">
<summary><span class="prism-os-icon"><svg viewBox="0 0 24 24"><ellipse cx="12" cy="15" rx="6" ry="7"/><circle cx="12" cy="7" r="3.2"/><ellipse cx="9.5" cy="16" rx="1.6" ry="2.4" fill="var(--prism-surface)"/><ellipse cx="14.5" cy="16" rx="1.6" ry="2.4" fill="var(--prism-surface)"/></svg></span>Linux</summary>

<div class="prism-os-body">

Download: `prism-studio-Linux.zip`

</div>
</details>

</div>

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

<div class="prism-os-grid">

<details class="prism-os-card">
<summary><span class="prism-os-icon"><svg viewBox="0 0 24 24"><path d="M16.7 12.4c0-2.7 2.2-4 2.3-4.1-1.3-1.9-3.3-2.1-4-2.2-1.7-.2-3.3 1-4.2 1-.9 0-2.2-1-3.6-1-1.9 0-3.6 1.1-4.5 2.7-1.9 3.3-.5 8.2 1.4 10.9.9 1.3 2 2.9 3.4 2.8 1.4-.1 1.9-.9 3.5-.9s2.1.9 3.5.9c1.5 0 2.4-1.4 3.3-2.7.6-.9 1-1.8 1.4-2.8-1.9-.7-2.5-2.6-2.5-2.6Z"/><path d="M13.9 4.1c.7-.9 1.2-2.1 1.1-3.3-1.1.1-2.3.7-3 1.6-.7.8-1.3 2.1-1.1 3.3 1.2.1 2.4-.6 3-1.6Z"/></svg></span>macOS / Linux</summary>

<div class="prism-os-body">

```bash
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
./setup.sh
source .venv/bin/activate
python prism-studio.py
```

</div>
</details>

<details class="prism-os-card">
<summary><span class="prism-os-icon"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="8" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/><rect x="13" y="13" width="8" height="8" rx="1"/></svg></span>Windows</summary>

<div class="prism-os-body">

```powershell
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
.\setup.ps1
.venv\Scripts\activate
python prism-studio.py
```

</div>
</details>

</div>

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

- [Getting Started](TUTORIAL_BEGINNER.md)
- [Studio Guide](studio/index.md)
- [CLI Reference](CLI_REFERENCE.md)
