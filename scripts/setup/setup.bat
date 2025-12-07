@echo off
::
:: Setup script for prism-validator on Windows
::
:: This script will:
:: 1. Check if 'uv' is installed.
:: 2. Create a virtual environment in .\.venv
:: 3. Install dependencies from requirements.txt into the virtual environment.

:: --- Configuration ---
set VENV_DIR=.venv
set REQUIREMENTS_FILE=requirements.txt

:: --- Main Script ---
echo INFO: Starting project setup for prism-validator...

:: 1. Check for uv
uv --version >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: 'uv' command not found.
    echo INFO: Please install uv first. See: https://github.com/astral-sh/uv
    echo INFO: Example installation (PowerShell): powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    exit /b 1
)
echo INFO: 'uv' is installed.

:: 2. Check for requirements.txt
if not exist "%REQUIREMENTS_FILE%" (
    echo ERROR: '%REQUIREMENTS_FILE%' not found.
    echo INFO: Please make sure the requirements file exists in the project root.
    exit /b 1
)
echo INFO: '%REQUIREMENTS_FILE%' found.

:: 3. Create virtual environment
echo INFO: Creating virtual environment in '%VENV_DIR%'...
uv venv %VENV_DIR%
if %errorlevel% neq 0 (
    echo ERROR: Failed to create virtual environment.
    exit /b 1
)
echo.
echo SUCCESS: Virtual environment created.

:: 4. Install dependencies
echo INFO: Installing dependencies from '%REQUIREMENTS_FILE%'...
call %VENV_DIR%\Scripts\activate.bat
uv pip install -r %REQUIREMENTS_FILE%
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    exit /b 1
)
call %VENV_DIR%\Scripts\deactivate.bat
echo SUCCESS: Dependencies installed successfully.

:: --- Final Instructions ---
echo.
echo --------------------------------------------------
echo Setup complete!
echo To activate the virtual environment, run:
echo %VENV_DIR%\Scripts\activate
echo --------------------------------------------------
