<#
.SYNOPSIS
    Start the File Validator web server (Windows PowerShell).
.DESCRIPTION
    Synchronises dependencies via uv, sets PYTHONPATH, and launches the
    FastAPI server in the requested environment (dev or prod).
.PARAMETER Env
    The environment to run in: dev (default) or prod.
.EXAMPLE
    .\start_server.ps1          # starts in dev mode
    .\start_server.ps1 prod     # starts in prod mode
#>
param(
    [ValidateSet("dev", "prod")]
    [string]$Env = "dev"
)

$ErrorActionPreference = 'Stop'

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot   = Resolve-Path "$scriptDir\.."
$mainModule = Join-Path $repoRoot "file-validator-webserver\src\file_validator_webserver\main.py"

Write-Host "================================"
Write-Host "Synchronizing dependencies..."
Push-Location $repoRoot
try { uv sync } finally { Pop-Location }
Write-Host "================================"

Write-Host "Script directory : $scriptDir"
Write-Host "Repository root  : $repoRoot"
Write-Host "Working directory: $(Get-Location)"

# Set PYTHONPATH so both packages are importable
$coreSrc = Join-Path $repoRoot "file-validator-core\src"
$webSrc  = Join-Path $repoRoot "file-validator-webserver\src"
$env:PYTHONPATH = "$coreSrc;$webSrc;$($env:PYTHONPATH)"
Write-Host "PYTHONPATH       : $env:PYTHONPATH"

Write-Host "================================"
Write-Host "Starting server in '$Env' environment..."
Write-Host "================================"

if ($Env -eq "dev") {
    Write-Host "Running in development mode..."
    uv run fastapi dev $mainModule `
        --app app `
        --host 127.0.0.1 `
        --port 9000
}
elseif ($Env -eq "prod") {
    Write-Host "Running in production mode..."
    uv run fastapi run $mainModule `
        --app app `
        --host 127.0.0.1 `
        --port 9290
}

Write-Host "================================"
Write-Host "Server stopped."
Write-Host "================================"
