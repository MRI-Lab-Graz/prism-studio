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

# 3. Check for requirements.txt
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo_error "'$REQUIREMENTS_FILE' not found."
    echo_info "Please make sure the requirements file exists in the project root."
    exit 1
fi
echo_info "'$REQUIREMENTS_FILE' found."

# 3. Create virtual environment
if [ -d "$VENV_DIR" ]; then
    echo_info "Virtual environment already exists in '$VENV_DIR' - reusing it."
else
    echo_info "Creating virtual environment in '$VENV_DIR'..."
    uv venv $VENV_DIR
    if [ $? -ne 0 ]; then
        echo_error "Failed to create virtual environment."
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

# Ensure pyreadstat is available for SPSS SAV export
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
