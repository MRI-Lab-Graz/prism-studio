# Installation

PRISM is designed to be easy to install on Windows, macOS, and Linux.

## Prerequisites

- **Python 3.8 or higher**: [Download Python](https://www.python.org/downloads/)
- **Deno** (for BIDS validation): [Download Deno](https://deno.com/) (Automatically installed by setup script)
- **Git** (optional, for cloning the repository): [Download Git](https://git-scm.com/downloads)

## Quick Install (Recommended)

### macOS / Linux

Open your terminal and run:

```bash
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
bash scripts/setup/setup.sh
```

### Windows

**Choose one of two installation methods depending on your use case:**

#### Option 1: Pre-Built Version (Normal Users)

If you just want to use PRISM for dataset validation:

```powershell
# Download the pre-built PrismValidator.exe from releases
# https://github.com/MRI-Lab-Graz/prism-studio/releases

# Extract the folder and run:
PrismValidator.exe "C:\path\to\your\dataset"
```

**Advantages:**
- No Python installation required
- Simple, single executable
- Minimal dependencies
- Easiest setup for end users

**Disadvantages:**
- Cannot modify the code
- Cannot install additional analysis tools
- Larger file size

#### Option 2: Development Installation (Developers)

If you want to contribute, modify code, or use additional development tools:

Open PowerShell and run:

```powershell
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio
.\setup.ps1 -Dev
```

This will:
1.  Create a Python virtual environment (`.venv`).
2.  Install all necessary dependencies for development.
3.  Install testing and documentation tools.
4.  Prepare the application for use and modification.

**Advantages:**
- Full source code access
- Can modify and extend functionality
- Includes development and testing tools
- Suitable for contributions

**Disadvantages:**
- Requires Python 3.8+ installation
- More dependencies to manage
- Slightly longer setup time

---

**Note:** The CLI tools (`prism.py`, `prism_tools.py`) intentionally enforce running from the repository-local virtual environment at `./.venv`.

## Manual Installation

If you prefer to set it up manually:

```bash
# 1. Clone the repository
git clone https://github.com/MRI-Lab-Graz/prism-studio.git
cd prism-studio

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate the environment
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt
```

## Verifying Installation

To check if everything is installed correctly, try running the help command:

```bash
# macOS/Linux
source .venv/bin/activate
python prism.py --help

# Windows
.venv\Scripts\activate
python prism.py --help
```

If you see the help message, you are ready to go!

## Troubleshooting

### Windows Antivirus / SmartScreen
If you are using the standalone `.exe` version on Windows, you might encounter warnings from Windows Defender or third-party antivirus software (like Norton). This is a common false positive for unsigned open-source software. 

Please refer to the [Windows Setup Guide](WINDOWS_SETUP.md#issue-antivirus-defender-norton-etc-blocks-the-exe) for detailed instructions on how to handle these warnings.
