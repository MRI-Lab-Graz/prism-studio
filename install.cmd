@echo off
REM One-click Windows setup and launch for PRISM Studio.
REM
REM This is the only Windows entry point - don't add another .cmd/.ps1
REM next to it, that's exactly the "which file do I run" confusion this
REM replaced (see scripts/setup/windows.ps1, which holds the actual logic).
REM
REM This is a .cmd, not a .ps1, on purpose: batch files are exempt from
REM PowerShell's execution policy, so this runs even on machines where a
REM bare .ps1 would be refused ("is not digitally signed" / "kann nicht
REM geladen werden"). Double-click it, or run it from any shell.
REM
REM Arguments are passed through to scripts\setup\windows.ps1,
REM e.g.  install.cmd -Build -Dev
REM
REM Kept free of parenthesised blocks and goto so it survives being saved
REM with Unix line endings.
setlocal
cd /d "%~dp0"

echo Removing the "downloaded from internet" mark from repository files...
powershell -NoProfile -Command "Get-ChildItem -Recurse | Unblock-File"

powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\setup\windows.ps1" %*
if errorlevel 1 echo.
if errorlevel 1 echo Setup failed - see the messages above.
if errorlevel 1 pause
if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\setup\create_desktop_shortcut.ps1"

call ".venv\Scripts\activate.bat"
python prism-studio.py
pause
