<#
.SYNOPSIS
    Start the File Validator web server (Windows PowerShell).
.DESCRIPTION
    Synchronises dependencies via uv, sets PYTHONPATH, and launches the
    FastAPI server in the requested environment (dev or prod).
.PARAMETER Env
    The environment to run in: dev or prod (default: prod).
.PARAMETER Port
    The port to run on (default: 9000 for dev, 9290 for prod).
.PARAMETER Host
    The host address to bind (default: 127.0.0.1 for dev, required for prod).
.EXAMPLE
    .\start_server.ps1
    .\start_server.ps1 -Env dev
    .\start_server.ps1 -Env prod -Host 0.0.0.0 -Port 8080
#>
param(
    [Alias("e")]
    [ValidateSet("dev", "prod")]
    [string]$Env = "prod",

    [Alias("p")]
    [int]$Port = 0,

    [Alias("h")]
    [string]$Host = ""
)

$ErrorActionPreference = 'Stop'
$ScriptName = $MyInvocation.MyCommand.Name

# Normalize environment to lowercase
$Env = $Env.ToLower()

# Validate environment
if ($Env -notin @("dev", "prod")) {
    Write-Error "Error: Invalid environment '$Env'. Must be 'dev' or 'prod'."
    exit 1
}

# Validate host for production environment
if ($Env -eq "prod" -and [string]::IsNullOrEmpty($Host)) {
    Write-Error "Error: Host must be specified for production environment"
    Write-Host "Use -Host to specify the host address"
    exit 1
}

# Set default port based on environment if not specified
if ($Port -eq 0) {
    if ($Env -eq "dev") {
        $Port = 9000
    } else {
        $Port = 9290
    }
}

# Set default host for dev environment if not specified
if ([string]::IsNullOrEmpty($Host) -and $Env -eq "dev") {
    $Host = "127.0.0.1"
}

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot   = Resolve-Path "$scriptDir\.."
$mainModule = Join-Path $repoRoot "file-validator-webserver\src\file_validator_webserver\main.py"

Write-Host "================================"
Write-Host "Synchronizing dependencies..."
Push-Location $repoRoot
try { uv sync } finally { Pop-Location }
Write-Host "================================"
Write-Host "Starting server in '$Env' environment..."

Write-Host "Script directory : $scriptDir"
Write-Host "Repository root  : $repoRoot"
Write-Host "Working directory: $(Get-Location)"

# Set PYTHONPATH so both packages are importable
$coreSrc = Join-Path $repoRoot "file-validator-core\src"
$webSrc  = Join-Path $repoRoot "file-validator-webserver\src"
$env:PYTHONPATH = "$coreSrc;$webSrc;$($env:PYTHONPATH)"
Write-Host "PYTHONPATH       : $env:PYTHONPATH"
Write-Host "Host             : $Host"
Write-Host "Port             : $Port"

if ($Env -eq "dev") {
    Write-Host "Running in development mode..."
    uv run fastapi dev $mainModule `
        --app app `
        --host $Host `
        --port $Port
}
elseif ($Env -eq "prod") {
    Write-Host "Running in production mode..."
    uv run fastapi run $mainModule `
        --app app `
        --host $Host `
        --port $Port
}

Write-Host "================================"
Write-Host "Server stopped."
Write-Host "================================"