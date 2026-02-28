@echo off
setlocal

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%\..\..
pushd "%REPO_ROOT%"

if not exist ".venv" (
  echo [ERROR] Missing .venv in %CD%
  echo Run setup first: scripts\setup\setup-windows.bat
  popd
  exit /b 1
)

call .venv\Scripts\activate.bat
python prism.py --help >nul
if errorlevel 1 (
  popd
  exit /b 1
)

python prism-studio.py --help >nul
if errorlevel 1 (
  popd
  exit /b 1
)

echo [OK] Local smoke checks passed (prism.py + prism-studio.py).

popd
exit /b 0
