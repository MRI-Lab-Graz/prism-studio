#!/bin/bash
#
# Setup script for prism on UNIX-like systems (Linux, macOS)
#
# This script will:
# 1. Check if 'uv' is installed (offers to install it if missing).
# 2. Create a virtual environment in ./.venv
# 3. Install dependencies from requirements.txt into the virtual environment.

# --- Configuration ---
VENV_DIR=".venv"
REQUIREMENTS_FILE="requirements.txt"
BUILD_REQUIREMENTS_FILE="requirements-build.txt"
DEV_REQUIREMENTS_FILE="requirements-dev.txt"

INSTALL_BUILD_DEPS=false
INSTALL_DEV_DEPS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build)
            INSTALL_BUILD_DEPS=true
            shift
            ;;
        --dev)
            INSTALL_DEV_DEPS=true
            shift
            ;;
        *)
            echo_error "Unknown argument: $1"
            echo "Usage: bash install.sh [--build] [--dev]"
            exit 1
            ;;
    esac
done

# --- Functions ---
echo_info() {
    echo "INFO: $1"
}

echo_error() {
    echo "ERROR: $1" >&2
}

echo_success() {
    echo "✅ $1"
}

fetch_url() {
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- "$1"
    else
        echo_error "Neither curl nor wget is available to download $1."
        return 1
    fi
}

ensure_uv() {
    # uv's installer puts it in ~/.local/bin, which a fresh shell may not have on PATH yet.
    export PATH="$PATH:$HOME/.local/bin:$HOME/.cargo/bin"
    command -v uv >/dev/null 2>&1 && return 0

    echo_info "'uv' (the tool this setup uses to install Python packages) is not installed."
    local answer=""
    read -r -p "Install uv now using its official installer (https://astral.sh/uv/install.sh)? [Y/n] " answer || answer="n"
    if [[ ! "$answer" =~ ^[Nn] ]]; then
        fetch_url https://astral.sh/uv/install.sh | sh
        command -v uv >/dev/null 2>&1 && return 0
        echo_error "Installing uv did not succeed."
    fi
    echo_info "Install uv by hand, then run 'bash install.sh' again."
    echo_info "Instructions (open in a web browser): https://docs.astral.sh/uv/getting-started/installation/"
    echo_info "With Homebrew on macOS you can also run: brew install uv"
    return 1
}

offer_datalad() {
    if command -v datalad >/dev/null 2>&1 && command -v git-annex >/dev/null 2>&1; then
        echo_info "DataLad and git-annex are already installed."
        return 0
    fi
    # Same command the app suggests, so installer and app never disagree.
    local cmd
    cmd="$("$VENV_PYTHON_UNIX" -c 'from src.datalad_doctor import install_command; print(install_command())')" || return 0
    echo_info "DataLad and git-annex (version control and backup for your project data) are highly recommended."
    local answer=""
    read -r -p "Install them now with '$cmd'? [Y/n] " answer || answer="n"
    if [[ "$answer" =~ ^[Nn] ]]; then
        echo_info "Skipped. You can install them later with: $cmd"
        return 0
    fi
    if $cmd; then
        uv tool update-shell >/dev/null 2>&1  # puts uv's tool folder on PATH for new terminals
        echo_success "DataLad and git-annex installed."
    else
        echo_error "Installing DataLad failed. You can retry later with: $cmd"
    fi
    if ! git --version >/dev/null 2>&1; then
        echo_info "DataLad also needs git: $("$VENV_PYTHON_UNIX" -c 'from src.datalad_doctor import git_install_hint; print(git_install_hint())')"
    fi
}

resolve_path() {
    local target="$1"
    if [ -z "$target" ]; then
        return 1
    fi

    if [ -d "$target" ]; then
        (
            cd "$target" && pwd -P
        )
        return
    fi

    local parent_dir
    parent_dir="$(dirname "$target")"
    local base_name
    base_name="$(basename "$target")"

    if [ -d "$parent_dir" ]; then
        (
            cd "$parent_dir" && printf "%s/%s\n" "$(pwd -P)" "$base_name"
        )
        return
    fi

    printf "%s\n" "$target"
}

resolve_base_python() {
    local candidate="$1"
    if [ ! -x "$candidate" ]; then
        return 1
    fi

    "$candidate" - <<'PY'
import sys

print(getattr(sys, "_base_executable", sys.executable))
PY
}

ensure_min_python_version() {
    local candidate="$1"

    "$candidate" - <<'PY'
import sys

# Upper bound: several pinned scientific wheels (pyedflib, ...) have no
# builds for Python 3.13+, and pip then falls back to a source build.
current = sys.version_info[:3]
if not ((3, 10) <= current[:2] <= (3, 12)):
    raise SystemExit(1)
print(f"{current[0]}.{current[1]}.{current[2]}")
PY
    local status=$?

    # Prefer an installed 3.10-3.12 over a uv-managed one: uv's Python can abort in
    # ensurepip with --copies on macOS, forcing the symlinked-venv fallback.
    if [ $status -ne 0 ] && [ -z "${PRISM_PYTHON:-}" ]; then
        local minor found
        for minor in 12 11 10; do
            found="$(PATH="$PATH:/opt/homebrew/bin:/usr/local/bin" command -v "python3.$minor" || true)"
            if [ -n "$found" ] && [ -x "$found" ]; then
                # A venv built through a symlink (uv's ~/.local/bin/python3.12 shim)
                # records the symlink's dir as `home` and cannot find its stdlib.
                while [ -L "$found" ]; do
                    local link
                    link="$(readlink "$found")"
                    case "$link" in
                        /*) found="$link" ;;
                        *) found="$(dirname "$found")/$link" ;;
                    esac
                done
                echo_success "Using installed Python 3.$minor: $found"
                VENV_CREATOR_PYTHON="$found"
                return 0
            fi
        done
    fi

    if [ $status -ne 0 ] && [ -z "${PRISM_PYTHON:-}" ] && command -v uv >/dev/null 2>&1; then
        echo_info "System Python ($candidate) is not 3.10-3.12; asking uv to provide one..."
        local uv_python
        uv_python="$(uv python find --system '>=3.10,<3.13' 2>/dev/null)"
        if [ -z "$uv_python" ]; then
            uv python install 3.12 && uv_python="$(uv python find --system '>=3.10,<3.13' 2>/dev/null)"
        fi
        if [ -n "$uv_python" ] && [ -x "$uv_python" ]; then
            echo_success "Using uv-managed Python: $uv_python"
            VENV_CREATOR_PYTHON="$uv_python"
            return 0
        fi
    fi

    if [ $status -ne 0 ]; then
        echo_error "Unsupported Python interpreter: $candidate"
        echo_error "PRISM source setup requires Python 3.10-3.12."
        echo_info "Install Python 3.10, 3.11 or 3.12 and rerun setup (or set PRISM_PYTHON to a compatible interpreter)."
        exit 1
    fi
}

is_python_executable_usable() {
    local candidate="$1"
    if [ ! -x "$candidate" ]; then
        return 1
    fi

    "$candidate" -c "import sys" >/dev/null 2>&1
}

# A symlinked venv python is fine (it is the fallback when --copies fails);
# a dangling link fails the usability check and the venv is recreated.
reset_unusable_venv() {
    [ -d "$VENV_DIR" ] || return 0
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        echo_info "Existing '$VENV_DIR' is missing activation files; recreating it."
        rm -rf "$VENV_DIR"
    elif ! is_python_executable_usable "$VENV_PYTHON_UNIX"; then
        echo_info "Existing '$VENV_DIR' has an unusable Python interpreter; recreating it."
        rm -rf "$VENV_DIR"
    else
        echo_info "Virtual environment already exists in '$VENV_DIR' - reusing it."
    fi
}

detect_package_manager() {
    if command -v apt-get >/dev/null 2>&1; then
        printf "apt"
    elif command -v dnf >/dev/null 2>&1; then
        printf "dnf"
    elif command -v pacman >/dev/null 2>&1; then
        printf "pacman"
    elif command -v zypper >/dev/null 2>&1; then
        printf "zypper"
    else
        printf "unknown"
    fi
}

suggest_install_venv_package() {
    local pyver="$1"
    local pm
    pm=$(detect_package_manager)
    case "$pm" in
        apt)
            if [ -n "$pyver" ]; then
                echo_info "On Debian/Ubuntu: sudo apt-get install python${pyver}-venv"
                echo_info "Or try: sudo apt-get install python3-venv"
            else
                echo_info "On Debian/Ubuntu: sudo apt-get install python3-venv"
            fi
            ;;
        dnf)
            echo_info "On Fedora/RHEL: sudo dnf install python3"
            echo_info "If that doesn't help, install the distro package that provides ensurepip/venv."
            ;;
        pacman)
            echo_info "On Arch Linux: sudo pacman -Syu python"
            ;;
        zypper)
            echo_info "On openSUSE: sudo zypper install python3-virtualenv"
            ;;
        *)
            echo_info "Install your distribution's 'python3-venv' or ensurepip support for the selected Python."
            ;;
    esac
    echo_info "After installing, rerun: bash install.sh"
}

create_virtualenv() {
    echo_info "Creating virtual environment in '$VENV_DIR'..."
    if [ ! -x "$VENV_CREATOR_PYTHON" ]; then
        echo_error "Python interpreter not executable: $VENV_CREATOR_PYTHON"
        exit 1
    fi

    if ! "$VENV_CREATOR_PYTHON" -c "import ensurepip" >/dev/null 2>&1; then
        pyver="$($VENV_CREATOR_PYTHON -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || true)"
        echo_error "The selected Python ($VENV_CREATOR_PYTHON) does not provide 'ensurepip', which venv needs to bootstrap pip."
        suggest_install_venv_package "$pyver"
        exit 1
    fi

    local allow_symlink=0
    if ! "$VENV_CREATOR_PYTHON" -m venv --copies "$VENV_DIR" 2>/dev/null; then
        # Copied interpreters can crash on some macOS setups (uv-managed Python aborts in ensurepip; confirmed on a user machine).
        echo_info "Venv with copied interpreter failed; retrying with a symlinked interpreter..."
        rm -rf "$VENV_DIR"
        allow_symlink=1
        "$VENV_CREATOR_PYTHON" -m venv "$VENV_DIR"
    fi
    if [ $? -ne 0 ]; then
        echo_error "Failed to create virtual environment."
        if ! "$VENV_CREATOR_PYTHON" -c "import ensurepip" >/dev/null 2>&1; then
            pyver="$($VENV_CREATOR_PYTHON -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || true)"
            echo_info "It appears ensurepip is missing from this Python build."
            suggest_install_venv_package "$pyver"
        fi
        exit 1
    fi

    if [ "$allow_symlink" -eq 0 ] && [ -L "$VENV_PYTHON_UNIX" ]; then
        echo_error "Virtual environment creation produced a symlinked Python ($VENV_PYTHON_UNIX)."
        echo_info "This setup requires a local venv Python binary."
        exit 1
    fi

    echo_success "Virtual environment created."
}

select_venv_creator_python() {
    local candidate=""
    local active_venv_abs=""
    local target_venv_abs=""
    local base_candidate=""

    if [ -n "${PRISM_PYTHON:-}" ]; then
        candidate="$PRISM_PYTHON"
    else
        candidate="$(command -v python3 || true)"
    fi

    target_venv_abs="$(resolve_path "$VENV_DIR")"
    if [ -n "${VIRTUAL_ENV:-}" ]; then
        active_venv_abs="$(resolve_path "$VIRTUAL_ENV")"
    fi

    if [ -n "$candidate" ] && {
        [[ "$candidate" == "$target_venv_abs/"* ]] || \
        { [ -n "$active_venv_abs" ] && [[ "$candidate" == "$active_venv_abs/"* ]]; }
    }; then
        base_candidate="$(resolve_base_python "$candidate" || true)"
        if [ -n "$base_candidate" ]; then
            echo_info "Current python points inside a virtual environment; using base Python: $base_candidate"
            candidate="$base_candidate"
        fi
    fi

    if [[ "$candidate" == *"/fsl/"* ]]; then
        if [ -x "/usr/bin/python3" ]; then
            candidate="/usr/bin/python3"
            echo_info "Detected FSL python in PATH, using system Python: $candidate"
        else
            echo_error "Detected FSL python in PATH and /usr/bin/python3 was not found."
            echo_info "Set PRISM_PYTHON to a non-FSL Python path and rerun setup."
            exit 1
        fi
    fi

    if [ -z "$candidate" ]; then
        echo_error "Could not find a usable python3 interpreter."
        echo_info "Set PRISM_PYTHON to a non-FSL Python path and rerun setup."
        exit 1
    fi

    VENV_CREATOR_PYTHON="$candidate"
}

# --- Main Script ---
echo_info "Starting project setup for prism..."

# 0. Clear stale bytecode caches so old .pyc files from a different Python version
#    cannot mask changes in the current source tree.
echo_info "Clearing stale __pycache__ directories..."
find . -path './.venv' -prune -o -type d -name '__pycache__' -print | xargs -r rm -rf
echo_success "__pycache__ cleared."

# 1. Check for uv
ensure_uv || exit 1
echo_info "'uv' is installed."

# 2. Check for Deno (Required for BIDS validation)
if ! command -v deno &> /dev/null; then
    echo_info "Deno not found (required for BIDS validation)."
    # Downloads and runs Deno's own installer script: ask first, never silently.
    read -r -p "Install Deno now using its official installer (https://deno.land/install.sh)? [y/N] " install_deno || install_deno=""
    if [[ "$install_deno" =~ ^[Yy]$ ]]; then
        fetch_url https://deno.land/install.sh | sh

        # Add to path for current session
        export DENO_INSTALL="$HOME/.deno"
        export PATH="$DENO_INSTALL/bin:$PATH"

        echo_success "Deno installed."
    else
        echo_info "Skipped. BIDS validation will not work until Deno is installed: https://deno.land"
    fi
else
    echo_info "Deno is already installed."
fi

# 2b. Check for tkinter (required for folder picker on Linux)
echo_info "Checking for tkinter (required for folder picker)..."
if [ "$(uname)" = "Darwin" ]; then
    echo_info "macOS uses the native folder picker; tkinter not needed."
elif python3 -c "import tkinter" 2>/dev/null; then
    echo_success "tkinter is available"
else
    echo "⚠️  WARNING: tkinter is NOT available"
    echo "⚠️  The web interface folder picker will not work."
    echo "⚠️  To fix on Ubuntu/Debian: sudo apt-get install python3-tk"
    echo "⚠️  To fix on Fedora/RHEL: sudo dnf install python3-tkinter"
    echo "⚠️  Or continue without it - you can enter paths manually."
    echo "Press Enter to continue anyway, or Ctrl+C to abort..."
    read -r
fi

# 3. Check for requirements.txt
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo_error "'$REQUIREMENTS_FILE' not found."
    echo_info "Please make sure the requirements file exists in the project root."
    exit 1
fi
echo_info "'$REQUIREMENTS_FILE' found."

# 3. Create virtual environment
VENV_CREATOR_PYTHON=""
select_venv_creator_python
ensure_min_python_version "$VENV_CREATOR_PYTHON"
VENV_PYTHON_UNIX="$VENV_DIR/bin/python"
reset_unusable_venv

if [ ! -d "$VENV_DIR" ]; then
    create_virtualenv
fi

# 4. Install dependencies
echo_info "Installing dependencies from '$REQUIREMENTS_FILE'..."
# Activate the venv to install packages into it
if ! source "$VENV_DIR/bin/activate" >/dev/null 2>&1; then
    echo_info "Failed to activate virtual environment; attempting to recreate it..."
    rm -rf "$VENV_DIR"
    create_virtualenv
    if ! source "$VENV_DIR/bin/activate" >/dev/null 2>&1; then
        echo_error "Could not activate virtual environment after recreation. Please inspect the Python installation or remove '$VENV_DIR' manually and retry."
        exit 1
    fi
fi

# Install core dependencies
uv pip install -r $REQUIREMENTS_FILE
if [ $? -ne 0 ]; then
    echo_error "Failed to install dependencies."
    exit 1
fi

# Ensure pyreadstat is available for SPSS SAVE export
uv pip install pyreadstat
if [ $? -ne 0 ]; then
    echo_error "Failed to install pyreadstat."
    exit 1
fi

if [ "$INSTALL_BUILD_DEPS" = true ]; then
    if [ ! -f "$BUILD_REQUIREMENTS_FILE" ]; then
        echo_error "'$BUILD_REQUIREMENTS_FILE' not found."
        exit 1
    fi
    echo_info "Installing build dependencies from '$BUILD_REQUIREMENTS_FILE'..."
    uv pip install -r $BUILD_REQUIREMENTS_FILE
    if [ $? -ne 0 ]; then
        echo_error "Failed to install build dependencies."
        exit 1
    fi
    echo_success "Build dependencies installed successfully."
fi

if [ "$INSTALL_DEV_DEPS" = true ]; then
    if [ ! -f "$DEV_REQUIREMENTS_FILE" ]; then
        echo_error "'$DEV_REQUIREMENTS_FILE' not found."
        exit 1
    fi
    echo_info "Installing development dependencies from '$DEV_REQUIREMENTS_FILE'..."
    uv pip install -r $DEV_REQUIREMENTS_FILE
    if [ $? -ne 0 ]; then
        echo_error "Failed to install development dependencies."
        exit 1
    fi
    echo_success "Development dependencies installed successfully."
fi

# Install the project in development mode (editable install)
echo_info "Installing prism in development mode..."
uv pip install -e .
if [ $? -ne 0 ]; then
    echo_error "Failed to install prism package. Check if setup.py exists."
    # Continue anyway as this is optional for direct script usage
fi

if [ -n "${VIRTUAL_ENV:-}" ]; then
    deactivate
fi
echo_success "Dependencies installed successfully."

# DataLad + git-annex (optional, highly recommended)
offer_datalad

# Desktop shortcut (optional; setup still succeeds without it)
bash scripts/setup/create_desktop_shortcut.sh || echo_info "Skipped Desktop shortcut."

# --- Final Instructions ---
echo ""
echo "--------------------------------------------------"
echo "Setup complete!"
echo "To activate the virtual environment, run:"
echo "source $VENV_DIR/bin/activate"
echo "Or double-click the PRISM Studio shortcut on your Desktop."
echo "--------------------------------------------------"
