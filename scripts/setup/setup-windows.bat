@echo off
::
:: Simple Windows setup script for prism-validator
:: Uses standard Python tools (no external dependencies like uv)
::

:: --- Configuration ---
set VENV_DIR=.venv
set REQUIREMENTS_FILE=requirements.txt

:: --- Functions (using labels) ---
goto :main

:echo_info
echo INFO: %~1
goto :eof

:echo_error
echo ERROR: %~1 >&2
goto :eof

:echo_success
echo ✓ %~1
goto :eof

:: --- Main Script ---
:main
call :echo_info "Starting project setup for prism-validator (Windows)..."

:: 1. Check for Python
python --version >nul 2>nul
if %errorlevel% neq 0 (
    call :echo_error "Python not found. Please install Python 3.8+ first."
    call :echo_info "Download from: https://www.python.org/downloads/"
    exit /b 1
)
call :echo_info "Python is installed."

:: 2. Check for requirements.txt
if not exist "%REQUIREMENTS_FILE%" (
    call :echo_error "'%REQUIREMENTS_FILE%' not found."
    call :echo_info "Please make sure the requirements file exists in the project root."
    exit /b 1
)
call :echo_info "'%REQUIREMENTS_FILE%' found."

:: 3. Create virtual environment
call :echo_info "Creating virtual environment in '%VENV_DIR%'..."
python -m venv %VENV_DIR%
if %errorlevel% neq 0 (
    call :echo_error "Failed to create virtual environment."
    exit /b 1
)
call :echo_success "Virtual environment created."

:: 4. Activate and install dependencies
call :echo_info "Activating virtual environment and installing dependencies..."
call %VENV_DIR%\Scripts\activate.bat

:: Upgrade pip first
python -m pip install --upgrade pip

:: Install core dependencies
pip install -r %REQUIREMENTS_FILE%
if %errorlevel% neq 0 (
    call :echo_error "Failed to install dependencies."
    call %VENV_DIR%\Scripts\deactivate.bat
    exit /b 1
)

:: Install the project in development mode
call :echo_info "Installing prism-validator in development mode..."
pip install -e .
if %errorlevel% neq 0 (
    call :echo_error "Failed to install prism-validator package."
    :: Continue anyway as this is optional for direct script usage
)

:: Install optional BIDS tooling
call :echo_info "Installing optional BIDS tooling (bidsschematools)..."
pip install bidsschematools
if %errorlevel% neq 0 (
    call :echo_error "Failed to install bidsschematools (optional)."
    call :echo_info "You can install it later with: pip install bidsschematools"
) else (
    call :echo_success "bidsschematools installed."
)

call %VENV_DIR%\Scripts\deactivate.bat
call :echo_success "Dependencies installed successfully."

:: --- Final Instructions ---
echo.
echo --------------------------------------------------
echo Setup complete!
echo To activate the virtual environment, run:
echo %VENV_DIR%\Scripts\activate
echo.
echo To run the validator:
echo python prism-validator.py /path/to/dataset
echo.
echo Windows-specific notes:
echo - Use backslashes or forward slashes for paths
echo - File paths with spaces should be quoted
echo - Example: python prism-validator.py "C:\My Data\dataset"
echo --------------------------------------------------

goto :eof