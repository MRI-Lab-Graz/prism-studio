Param(
    [string]$OutputZip = 'prism-windows-portable.zip'
)

Write-Host "Assembling portable Windows distribution..."

$cwd = (Get-Location).Path
$outDir = Join-Path $cwd 'dist\\prism-windows-portable'

if (Test-Path $outDir) {
    Write-Host "Removing existing $outDir"
    Remove-Item -Recurse -Force $outDir
}

New-Item -ItemType Directory -Path $outDir | Out-Null

# Create venv
Write-Host "Creating virtual environment..."
python -m venv "$outDir\\prism-venv"

$venvPython = Join-Path $outDir 'prism-venv\\Scripts\\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Error "python.exe not found in venv. Aborting."
    exit 1
}

Write-Host "Upgrading pip and installing dependencies into venv..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

Write-Host "Installing project into venv..."
& $venvPython -m pip install .

Write-Host "Pruning pip cache to reduce size..."
& $venvPython -m pip cache purge

# Aggressive pruning to reduce distribution size
Write-Host "Cleaning up venv (remove __pycache__, .pyc, tests, docs, examples)..."
$sitePackages = Join-Path $outDir 'prism-venv\Lib\site-packages'
if (Test-Path $sitePackages) {
    # Remove __pycache__ directories
    Get-ChildItem -Path $sitePackages -Recurse -Directory -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ieq '__pycache__' } | ForEach-Object { Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue }

    # Remove .pyc files
    Get-ChildItem -Path $sitePackages -Recurse -Include *.pyc -File -Force -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item -Force $_.FullName -ErrorAction SilentlyContinue }

    # Remove common non-runtime folders (tests, docs, examples)
    Get-ChildItem -Path $sitePackages -Recurse -Directory -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^(tests?|docs?|examples?)$' } | ForEach-Object { Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue }

    # Remove package data that is commonly large (locale docs, .dist-info if you accept risk)
    # NOTE: keeping .dist-info to avoid breaking entry points; do not remove unless you know it's safe.
}

# Copy minimal runtime files (entry script and web UI assets)
Write-Host "Copying runtime files (excluding large developer folders)..."
Copy-Item -Path prism-studio.py -Destination $outDir -Force
if (Test-Path 'app') {
    # Copy only templates and static assets; skip node_modules or frontend build folders
    $appDest = Join-Path $outDir 'app'
    New-Item -ItemType Directory -Path $appDest | Out-Null
    if (Test-Path 'app\templates') { Copy-Item -Path 'app\templates' -Destination $appDest\templates -Recurse -Force }
    if (Test-Path 'app\static') { Copy-Item -Path 'app\static' -Destination $appDest\static -Recurse -Force }
    # Copy any small config files
    Get-ChildItem -Path app -File -Force | Where-Object { $_.Name -in @('prism_studio_settings.json') } | ForEach-Object { Copy-Item -Path $_.FullName -Destination $appDest -Force }
}

# Create launcher
$launcher = @'
@echo off
set VENV=%~dp0prism-venv
"%VENV%\\Scripts\\python.exe" "%~dp0prism-studio.py" %*
'@

$launcherPath = Join-Path $outDir 'run_prism.bat'
Set-Content -Path $launcherPath -Value $launcher -Encoding ASCII

# Create short README
$readme = @(
    "Prism Portable",
    "Unzip this folder anywhere and double-click run_prism.bat to start the app.",
    "If the app fails, open a PowerShell window and run run_prism.bat to see errors."
)
Set-Content -Path (Join-Path $outDir 'README_SHORT.txt') -Value $readme -Encoding UTF8

Write-Host "Creating ZIP archive $OutputZip..."
if (Test-Path $OutputZip) { Remove-Item $OutputZip -Force }
Compress-Archive -Path (Join-Path $outDir '*') -DestinationPath $OutputZip

Write-Host "Portable ZIP created: $OutputZip"