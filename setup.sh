#!/bin/bash
#
# Setup script for prism on UNIX-like systems (Linux, macOS)
#
# This script will:
# 1. Check if 'uv' is installed.
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
            echo "Usage: bash setup.sh [--build] [--dev]"
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

# 1. Check for uv
if ! command -v uv &> /dev/null; then
    echo_error "'uv' command not found."
    echo_info "Please install uv first. See: https://github.com/astral-sh/uv"
    echo_info "Example installation: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo_info "'uv' is installed."

# 2. Check for Deno (Required for BIDS validation)
if ! command -v deno &> /dev/null; then
    echo_info "Deno not found (required for BIDS validation). Installing..."
    curl -fsSL https://deno.land/install.sh | sh
    
    # Add to path for current session
    export DENO_INSTALL="$HOME/.deno"
    export PATH="$DENO_INSTALL/bin:$PATH"
    
    echo_success "Deno installed."
else
    echo_info "Deno is already installed."
fi

# 2b. Check for tkinter (required for folder picker on Linux)
echo_info "Checking for tkinter (required for folder picker)..."
if python3 -c "import tkinter" 2>/dev/null; then
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
VENV_PYTHON_UNIX="$VENV_DIR/bin/python"
if [ -d "$VENV_DIR" ]; then
    if [ -L "$VENV_PYTHON_UNIX" ]; then
        echo_info "Existing '$VENV_DIR' uses a symlinked Python interpreter; recreating strict local venv."
        rm -rf "$VENV_DIR"
    else
        echo_info "Virtual environment already exists in '$VENV_DIR' - reusing it."
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo_info "Creating virtual environment in '$VENV_DIR'..."
    if [ ! -x "$VENV_CREATOR_PYTHON" ]; then
        echo_error "Python interpreter not executable: $VENV_CREATOR_PYTHON"
        exit 1
    fi

    "$VENV_CREATOR_PYTHON" -m venv --copies "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo_error "Failed to create virtual environment."
        exit 1
    fi

    if [ -L "$VENV_PYTHON_UNIX" ]; then
        echo_error "Virtual environment creation produced a symlinked Python ($VENV_PYTHON_UNIX)."
        echo_info "This setup requires a local venv Python binary."
        exit 1
    fi

    echo_success "Virtual environment created."
fi

# 4. Install dependencies
echo_info "Installing dependencies from '$REQUIREMENTS_FILE'..."
# Activate the venv to install packages into it
source $VENV_DIR/bin/activate

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

deactivate
echo_success "Dependencies installed successfully."

# --- Final Instructions ---
echo ""
echo "--------------------------------------------------"
echo "Setup complete!"
echo "To activate the virtual environment, run:"
echo "source $VENV_DIR/bin/activate"
echo "--------------------------------------------------"
