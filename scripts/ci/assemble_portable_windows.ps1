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

# Use the already built PyInstaller runtime to ensure true portability.
$runtimeCandidates = @(
    (Join-Path $cwd 'dist\\PrismStudio'),
    (Join-Path $cwd 'dist\\PrismValidator')
)

$distRuntime = $null
foreach ($candidate in $runtimeCandidates) {
    if (Test-Path $candidate) {
        $distRuntime = $candidate
        break
    }
}

if (-not $distRuntime) {
    Write-Error "Expected runtime folder not found. Build step must create dist\\PrismStudio (or dist\\PrismValidator for compatibility)."
    exit 1
}

Write-Host "Copying PyInstaller runtime from $distRuntime ..."
Copy-Item -Path (Join-Path $distRuntime '*') -Destination $outDir -Recurse -Force

$exeCandidates = @(
    (Join-Path $outDir 'PrismStudio.exe'),
    (Join-Path $outDir 'PrismValidator.exe')
)

$exeName = $null
foreach ($candidate in $exeCandidates) {
    if (Test-Path $candidate) {
        $exeName = Split-Path $candidate -Leaf
        break
    }
}

if (-not $exeName) {
    Write-Error "Neither PrismStudio.exe nor PrismValidator.exe found in portable output. Aborting."
    exit 1
}

# Create launcher
$launcher = @'
@echo off
set EXE=%~dp0__EXE_NAME__
if not exist "%EXE%" (
    echo __EXE_NAME__ not found next to this launcher.
  exit /b 1
)
"%EXE%" %*
'@

$launcher = $launcher.Replace('__EXE_NAME__', $exeName)
$launcher = $launcher.Replace('"%EXE%" %*', '"%EXE%" --force-clean-start %*')

$launcherPath = Join-Path $outDir 'run_prism.bat'
Set-Content -Path $launcherPath -Value $launcher -Encoding ASCII

# Create short README
$readme = @(
    "Prism Portable",
    "Unzip this folder anywhere and double-click run_prism.bat to start the app.",
    "This portable package does not require a system Python installation.",
    "If the app fails, open PowerShell in this folder and run .\\run_prism.bat to see errors."
)
Set-Content -Path (Join-Path $outDir 'README_SHORT.txt') -Value $readme -Encoding UTF8

Write-Host "Creating ZIP archive $OutputZip..."
if (Test-Path $OutputZip) { Remove-Item $OutputZip -Force }

# Give antivirus/Defender a moment to finish scanning freshly copied files.
# Compress-Archive (PS5) fails with PermissionDenied if any file is still locked.
Start-Sleep -Seconds 3

# Use .NET ZipFile directly — more robust than Compress-Archive on Windows.
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($outDir, (Join-Path $cwd $OutputZip))
    Write-Host "Portable ZIP created: $OutputZip"
} catch {
    Write-Warning "ZipFile failed: $_"
    Write-Host "Falling back to Compress-Archive..."
    Compress-Archive -Path (Join-Path $outDir '*') -DestinationPath $OutputZip
    Write-Host "Portable ZIP created: $OutputZip"
}