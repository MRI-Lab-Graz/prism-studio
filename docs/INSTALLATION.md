# Installation

Use this page to get PRISM Studio running in the simplest way.

This page is written for beginners. Use the written guide here for the full setup. Use the companion videos for quick hands-on examples.

## Standard installation

The standard installation path is the precompiled release from GitHub.

Use the latest release here:

- <https://github.com/MRI-Lab-Graz/prism-studio/releases/latest>

For most users, this is the right choice.

You do not need to clone the repository or install Python packages first.

## What to do

1. Open the latest release page.
2. Download the file for your operating system.
3. Extract the ZIP file.
4. Start PRISM Studio from the extracted folder.

## Which release should I choose?

Choose the ZIP file that matches your computer.

Typical release names are:

- `prism-studio-macOS-AppleSilicon.zip`
- `prism-studio-macOS-AppleIntel.zip`
- `prism-studio-Windows.zip`
- `prism-studio-Linux.zip`

## macOS: Apple Silicon or Intel?

macOS users often need to check this once.

To find out:

1. Open the Apple menu.
2. Select `About This Mac`.
3. Look at the chip or processor entry.

Choose the release like this:

- if you see `Apple M1`, `Apple M2`, `Apple M3`, or `Apple M4`, choose `AppleSilicon`
- if you see `Intel`, choose `AppleIntel`

Simple rule:

- Apple chip with `M` in the name: `AppleSilicon`
- Intel chip: `AppleIntel`

## Windows and Linux

For most users:

- Windows: choose `prism-studio-Windows.zip`
- Linux: choose `prism-studio-Linux.zip`

## First start on macOS

macOS may block downloaded apps the first time.

If that happens, use the helper included in the extracted release folder:

- `Prism Studio Installer.app`
- or `Open Prism Studio.command`

If needed, you can also right-click `PrismStudio.app` and choose Open once.

## Check that it worked

If PRISM Studio starts and opens the interface, the installation worked.

If the browser does not open automatically, go to:

- `http://localhost:5001`

## Advanced installation

Use the options below only when you need something beyond the normal release download.

## Python requirement for source installs

Source installation requires Python 3.10 or newer.

- Python 3.9 is not supported.
- If your current default Python is older, install Python 3.10+ and rerun the setup script.

## Advanced: source installation

Use source installation when you need:

- local code changes
- development work
- direct repository access
- advanced CLI usage from the source tree

### macOS and Linux

```bash
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
./setup.sh
source .venv/bin/activate
python prism-studio.py
```

### Windows

```powershell
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
.\setup.ps1
.venv\Scripts\activate
python prism-studio.py
```

## Advanced: CLI after source install

After the source install is working, you can also use the CLI tools.

Common examples:

```bash
python prism-validator /path/to/dataset
python prism_tools.py recipes surveys --prism /path/to/dataset
```

Use the CLI reference when you need more commands.

## Why the virtual environment matters for source installs

For source use, PRISM expects the repo-local virtual environment.

That means:

- macOS and Linux: `source .venv/bin/activate`
- Windows: `.venv\Scripts\activate`

If you skip this step, command-line tools may run with the wrong environment.

## Updating a source install

If you work from the repository, pull the changes and run the setup script again.

Typical update pattern:

```bash
git pull
./setup.sh
```

On Windows, use `setup.ps1` instead.

## Common beginner problems

### I do not know which macOS build I need

Open `About This Mac` and check whether the machine says `Apple M...` or `Intel`.

### The app starts but no browser page appears

Open this address manually:

- `http://localhost:5001`

### Python or package errors during source install

Use the precompiled release unless you specifically need the source version.

If you do need source, activate `.venv` before running commands.

## What to do next

After installation, the normal order is:

1. create or open a project
2. import data
3. validate the dataset
4. run scoring if needed

## Related pages

- Projects: [PROJECTS.md](PROJECTS.md)
- Studio overview: [STUDIO_OVERVIEW.md](STUDIO_OVERVIEW.md)
- CLI reference: [CLI_REFERENCE.md](CLI_REFERENCE.md)