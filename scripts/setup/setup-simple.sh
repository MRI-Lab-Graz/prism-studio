#!/bin/bash
#
# Simple setup script for prism-validator using standard Python tools
# Fallback for systems without 'uv'
#

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
echo_info "Starting project setup for prism-validator (standard Python)..."

# 1. Check for Python
if ! command -v python3 &> /dev/null; then
    echo_error "'python3' command not found."
    echo_info "Please install Python 3.8+ first."
    exit 1
fi
echo_info "Python 3 is installed."

# 2. Check for requirements.txt
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo_error "'$REQUIREMENTS_FILE' not found."
    echo_info "Please make sure the requirements file exists in the project root."
    exit 1
fi
echo_info "'$REQUIREMENTS_FILE' found."

# 3. Create virtual environment
echo_info "Creating virtual environment in '$VENV_DIR'..."
python3 -m venv $VENV_DIR
if [ $? -ne 0 ]; then
    echo_error "Failed to create virtual environment."
    exit 1
fi
echo_success "Virtual environment created."

# 4. Activate and install dependencies
echo_info "Activating virtual environment and installing dependencies..."
source $VENV_DIR/bin/activate

# Upgrade pip first
python -m pip install --upgrade pip

# Install core dependencies
pip install -r $REQUIREMENTS_FILE
if [ $? -ne 0 ]; then
    echo_error "Failed to install dependencies."
    exit 1
fi

# Install the project in development mode (editable install)
echo_info "Installing prism-validator in development mode..."
pip install -e .
if [ $? -ne 0 ]; then
    echo_error "Failed to install prism-validator package. Check if setup.py exists."
    # Continue anyway as this is optional for direct script usage
fi

# Install optional BIDS tooling
echo_info "Installing optional BIDS tooling (bidsschematools)..."
pip install bidsschematools
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
echo ""
echo "To run the validator:"
echo "python3 prism-validator-streamlined.py /path/to/dataset"
echo "or"
echo "python3 prism-validator.py /path/to/dataset"
echo "--------------------------------------------------"