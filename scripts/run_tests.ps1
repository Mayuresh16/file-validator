# Test runner script for file-validator project (PowerShell)
# Executes pytest with workspace dependencies synchronized

param(
    [string]$TestType = "all",
    [switch]$Verbose = $false
)

Write-Host "================================"
Write-Host "Synchronizing dependencies..."
uv sync
Write-Host "================================"

# Get the directory where this script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Get the repository root (parent of scripts directory)
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "Script directory: $ScriptDir"
Write-Host "Repository root: $RepoRoot"
Write-Host "Current working directory: $(Get-Location)"

# Set PYTHONPATH to include src directories from both packages
$env:PYTHONPATH = "$env:PYTHONPATH;$RepoRoot\file-validator-core\src;$RepoRoot\file-validator-webserver\src"
Write-Host "PYTHONPATH: $env:PYTHONPATH"

Write-Host "================================"
Write-Host "Running tests..."
Write-Host "================================"

# Build pytest command with optional verbosity flag
$PytestCmd = "uv run pytest"
if ($Verbose) {
    $PytestCmd = "$PytestCmd -vv"
}

switch ($TestType.ToLower()) {
    "core" {
        Write-Host "Running file-validator-core tests..."
        & cmd /c "$PytestCmd `"$RepoRoot\file-validator-core\tests`" --rootdir=`"$RepoRoot`""
    }
    "webserver" {
        Write-Host "Running file-validator-webserver tests..."
        & cmd /c "$PytestCmd `"$RepoRoot\file-validator-webserver\tests`" --rootdir=`"$RepoRoot`""
    }
    default {
        Write-Host "Running all tests..."
        & cmd /c "$PytestCmd `"$RepoRoot`" --rootdir=`"$RepoRoot`""
    }
}

$ExitCode = $LASTEXITCODE

Write-Host "================================"
if ($ExitCode -eq 0) {
    Write-Host "Tests completed successfully."
} else {
    Write-Host "Tests failed with exit code: $ExitCode"
}
Write-Host "================================"

exit $ExitCode

