@echo off
REM Start PRISM Studio on Windows (run setup.cmd once first).
REM
REM Double-click it, or run it from any shell. Arguments are passed
REM through to prism-studio.py.
REM
REM Kept free of parenthesised blocks and goto so it survives being saved
REM with Unix line endings.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" echo No virtual environment found in .venv
if not exist ".venv\Scripts\activate.bat" echo Run setup.cmd first to install PRISM Studio.
if not exist ".venv\Scripts\activate.bat" pause
if not exist ".venv\Scripts\activate.bat" exit /b 1

call ".venv\Scripts\activate.bat"
python prism-studio.py %*
pause
