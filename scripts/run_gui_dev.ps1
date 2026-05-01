<#
.SYNOPSIS
    Bring up the SCAFAD GUI backend (8088) and frontend (5173) for local
    development.

.DESCRIPTION
    The script seeds the SQLite demo database (unless -NoSeed is passed),
    launches Uvicorn for the FastAPI backend, then starts the Vite dev server
    in the foreground so Ctrl+C stops both processes cleanly.

.PARAMETER NoSeed
    Skip running the demo seeder before starting the backend.

.EXAMPLE
    PS> ./scripts/run_gui_dev.ps1
    PS> ./scripts/run_gui_dev.ps1 -NoSeed
#>

[CmdletBinding()]
param(
    [switch]$NoSeed
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$env:PYTHONPATH = "$RepoRoot;$RepoRoot/scafad;$($env:PYTHONPATH)"

if (-not $NoSeed) {
    Write-Host "[gui-dev] seeding demo detections via the real runtime..."
    python -m scafad.gui.backend.seed
}

Write-Host "[gui-dev] backend  -> http://127.0.0.1:8088 (uvicorn)"
$backend = Start-Process -PassThru -NoNewWindow `
    -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "scafad.gui.backend.main:app", "--host", "127.0.0.1", "--port", "8088", "--reload"

try {
    Set-Location (Join-Path $RepoRoot "scafad/gui/frontend")
    if (-not (Test-Path "node_modules")) {
        Write-Host "[gui-dev] installing frontend dependencies (one-time, ~60s)..."
        npm install --no-audit --no-fund
    }
    Write-Host "[gui-dev] frontend -> http://127.0.0.1:5173 (vite)"
    npm run dev
}
finally {
    if ($backend -and -not $backend.HasExited) {
        Write-Host "[gui-dev] stopping backend pid=$($backend.Id)"
        try { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue } catch {}
    }
}
