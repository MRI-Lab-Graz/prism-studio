#!/bin/bash
#
# Setup script for psycho-validator on UNIX-like systems (Linux, macOS)
#
# This script will:
# 1. Check if 'uv' is installed.
# 2. Create a virtual environment in ./.venv
# 3. Install dependencies from requirements.txt into the virtual environment.

# --- Configuration ---
VENV_DIR=".venv"
REQUIREMENTS_FILE="requirements.txt"

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
echo_info "Starting project setup for psycho-validator..."

# 1. Check for uv
if ! command -v uv &> /dev/null; then
    echo_error "'uv' command not found."
    echo_info "Please install uv first. See: https://github.com/astral-sh/uv"
    echo_info "Example installation: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo_info "'uv' is installed."

# 2. Check for requirements.txt
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo_error "'$REQUIREMENTS_FILE' not found."
    echo_info "Please make sure the requirements file exists in the project root."
    exit 1
fi
echo_info "'$REQUIREMENTS_FILE' found."

# 3. Create virtual environment
echo_info "Creating virtual environment in '$VENV_DIR'..."
uv venv $VENV_DIR
if [ $? -ne 0 ]; then
    echo_error "Failed to create virtual environment."
    exit 1
fi
echo_success "Virtual environment created."

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

# Install the project in development mode (editable install)
echo_info "Installing psycho-validator in development mode..."
uv pip install -e .
if [ $? -ne 0 ]; then
    echo_error "Failed to install psycho-validator package. Check if setup.py exists."
    # Continue anyway as this is optional for direct script usage
fi

# Ensure bidsschematools is available for --bids-schema support
echo_info "Installing optional BIDS tooling (bidsschematools)..."
uv pip install bidsschematools
if [ $? -ne 0 ]; then
    echo_error "Failed to install bidsschematools (optional). You can install it later with: pip install bidsschematools"
else
    echo_success "bidsschematools installed."
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
