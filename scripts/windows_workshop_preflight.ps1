$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = Join-Path $ScriptDir "setup/windows_workshop_preflight.ps1"

if (-not (Test-Path $Target)) {
    Write-Host "Moved script not found: $Target" -ForegroundColor Red
    exit 1
}

& $Target @args
exit $LASTEXITCODE
