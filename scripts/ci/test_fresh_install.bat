@echo off
REM Simulate fresh installation test (Windows)
REM This script tests the installation process from scratch

echo ========================================
echo PRISM Fresh Installation Simulation
echo ========================================
echo.

echo This script will:
echo   1. Backup current .venv
echo   2. Delete .venv
echo   3. Run setup.ps1
echo   4. Verify installation
echo   5. Restore backup if needed
echo.

set /p CONFIRM="Continue? (y/n): "
if /i not "%CONFIRM%"=="y" (
    echo Cancelled.
    exit /b 0
)

echo.
echo [1/5] Backing up current .venv...
if exist .venv (
    if exist .venv.backup (
        echo Removing old backup...
        rmdir /s /q .venv.backup
    )
    echo Renaming .venv to .venv.backup...
    move .venv .venv.backup > nul
    echo ✓ Backup created
) else (
    echo No existing .venv found - fresh installation
)

echo.
echo [2/5] Running setup.ps1...
echo.
powershell -ExecutionPolicy Bypass -File setup.ps1
set SETUP_EXIT=%ERRORLEVEL%

if %SETUP_EXIT% neq 0 (
    echo.
    echo ❌ Setup failed!
    echo.
    set /p RESTORE="Restore backup? (y/n): "
    if /i "%RESTORE%"=="y" (
        if exist .venv.backup (
            if exist .venv rmdir /s /q .venv
            move .venv.backup .venv > nul
            echo ✓ Backup restored
        )
    )
    exit /b %SETUP_EXIT%
)

echo.
echo [3/5] Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo [4/5] Verifying installation...
echo.

echo Checking PRISM...
python prism.py --help > nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo ✓ PRISM command works
) else (
    echo ✗ PRISM command failed
)

echo.
echo Checking pyedflib...
python -c "import pyedflib; print('✓ pyedflib version:', pyedflib.__version__)" 2> nul
if %ERRORLEVEL% neq 0 (
    echo ✗ pyedflib not available
    echo   RAW files will be copied instead of converted to EDF
)

echo.
echo Checking other core dependencies...
python -c "import flask; import pandas; import jsonschema; print('✓ Core dependencies OK')" 2> nul
if %ERRORLEVEL% neq 0 (
    echo ✗ Some core dependencies missing
)

echo.
echo [5/5] Installation test complete!
echo.

set /p KEEP="Keep new installation? (y/n): "
if /i not "%KEEP%"=="y" (
    if exist .venv.backup (
        echo Restoring backup...
        rmdir /s /q .venv
        move .venv.backup .venv > nul
        echo ✓ Backup restored
    )
) else (
    if exist .venv.backup (
        echo Removing backup...
        rmdir /s /q .venv.backup
        echo ✓ Backup removed
    )
)

echo.
echo ========================================
echo To use PRISM:
echo   1. Activate venv: .venv\Scripts\activate
echo   2. Run validator: python prism.py [dataset-path]
echo   3. Or web UI: python prism-studio.py
echo ========================================
