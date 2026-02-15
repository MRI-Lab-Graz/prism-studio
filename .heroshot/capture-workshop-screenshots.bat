@echo off
REM PRISM Workshop - Heroshot Screenshot Capture Helper (Windows)
REM This script starts PRISM Studio and captures all workshop screenshots

setlocal enabledelayedexpansion

echo.
echo 🎬 PRISM Workshop Heroshot Helper (Windows)
echo ==========================================
echo.

REM Get script directory
set SCRIPT_DIR=%~dp0
for %%F in ("%SCRIPT_DIR:~0,-1%") do set PROJECT_ROOT=%%~dpF

REM Check Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Node.js not found. Install from: https://nodejs.org/
    exit /b 1
)
for /f "tokens=*" %%i in ('node -v') do set NODE_VERSION=%%i
echo ✓ Node.js %NODE_VERSION%

REM Check npm
where npm >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ npm not found
    exit /b 1
)
for /f "tokens=*" %%i in ('npm -v') do set NPM_VERSION=%%i
echo ✓ npm %NPM_VERSION%

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    where python3 >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ Python not found
        exit /b 1
    )
    for /f "tokens=*" %%i in ('python3 --version') do set PY_VERSION=%%i
    set PYTHON_CMD=python3
) else (
    for /f "tokens=*" %%i in ('python --version') do set PY_VERSION=%%i
    set PYTHON_CMD=python
)
echo ✓ %PY_VERSION%

echo.

REM Check venv
if not exist "%PROJECT_ROOT%\.venv" (
    echo ❌ Virtual environment not found at %PROJECT_ROOT%\.venv
    echo Run: cd %PROJECT_ROOT% ^&^& python -m venv .venv
    exit /b 1
)
echo ✓ Virtual environment found

echo.
echo 📦 Installing Heroshot (if needed)...
call npm install -g heroshot@0.13.1 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo (Installing Heroshot globally...)
    call npm install -g heroshot@0.13.1
)
echo ✓ Heroshot ready

echo.
echo 🚀 Starting PRISM Studio...
cd /d "%PROJECT_ROOT%"
call .venv\Scripts\activate.bat
start /B python prism-studio.py >nul 2>&1

REM Get PRISM PID (Windows doesn't make this easy)
timeout /t 3 /nobreak
echo    Waiting for startup...

REM Wait for PRISM to be ready
echo.
echo ⏳ Waiting for PRISM Studio to be ready...
setlocal enabledelayedexpansion
set /a max_attempts=30
set /a attempt=0

:wait_prism
if !attempt! GEQ !max_attempts! (
    echo ❌ PRISM Studio failed to start
    exit /b 1
)

powershell -Command "try { (New-Object Net.WebClient).DownloadString('http://127.0.0.1:5001/') | Out-Null; exit 0 } catch { exit 1 }"
if %ERRORLEVEL% EQU 0 (
    echo ✓ PRISM Studio is ready at http://127.0.0.1:5001
    goto prism_ready
)

set /a attempt=!attempt!+1
echo    Attempt !attempt!/%max_attempts%...
timeout /t 2 /nobreak
goto wait_prism

:prism_ready
echo.
echo 📸 Capturing screenshots...
echo.

cd /d "%SCRIPT_DIR%"

REM Check if config exists
if not exist "config.json" (
    echo ❌ config.json not found in %SCRIPT_DIR%
    exit /b 1
)

REM Run Heroshot
npx heroshot --config config.json --clean
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Heroshot failed
    exit /b 1
)

echo.
echo ✓ Screenshots captured successfully!
echo.
echo 📁 Screenshots saved to:
echo    %PROJECT_ROOT%\docs\_static\screenshots\
echo.
echo 📝 Next steps:
echo    1. Review screenshots: dir ..\docs\_static\screenshots\
echo    2. Commit changes: git add docs\_static\screenshots\
echo    3. Commit with message: git commit -m "chore(docs): update workshop screenshots"
echo.

endlocal
