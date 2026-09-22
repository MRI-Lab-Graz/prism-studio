<#
.SYNOPSIS
    Creates a Desktop shortcut that launches PRISM Studio, using the app icon.

.DESCRIPTION
    Points at start.cmd in the repository root, so the shortcut keeps working
    after updates. Re-running this overwrites the existing shortcut.

.PARAMETER Name
    Shortcut name (without .lnk). Defaults to "PRISM Studio".
#>
Param(
    [string]$Name = "PRISM Studio"
)

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Target = Join-Path $RepoRoot "start.cmd"
$Icon = Join-Path $RepoRoot "app\static\prism2026.ico"

if (-not (Test-Path $Target)) {
    Write-Host "ERROR: start.cmd not found at '$Target'." -ForegroundColor Red
    exit 1
}

$LinkPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "$Name.lnk"

try {
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($LinkPath)
    $Shortcut.TargetPath = $Target
    $Shortcut.WorkingDirectory = $RepoRoot
    $Shortcut.Description = "Launch PRISM Studio"
    if (Test-Path $Icon) {
        $Shortcut.IconLocation = $Icon
    }
    $Shortcut.Save()
    Write-Host "Desktop shortcut created: $LinkPath" -ForegroundColor Green
} catch {
    Write-Host "WARNING: Could not create the Desktop shortcut: $_" -ForegroundColor Yellow
    exit 1
}
