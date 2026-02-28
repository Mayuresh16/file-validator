<#
PowerShell helper to clean stale build metadata and run `uv sync` for Windows users.
Run this from PowerShell (preferably Git Bash or Windows Terminal) with:
  ./tools/uv_sync_fix.ps1
#>

param()

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path "$scriptDir\.."
Set-Location $repoRoot
Write-Host "Repo root: $repoRoot"

if (-not (Test-Path "pyproject.toml")) {
    Write-Error "pyproject.toml not found in repo root ($repoRoot). Run from the repository root."
    exit 2
}

Write-Host "Cleaning stale build/egg-info artifacts..."
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "file-validator-webserver\src\file_validator_webserver.egg-info"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "file-validator-core\src\file_validator.egg-info"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "file-validator-webserver\build","file-validator-webserver\dist","file-validator-core\build","file-validator-core\dist"

Write-Host "Removing package-level uv.lock files (if present)..."
Remove-Item -Force -ErrorAction SilentlyContinue "file-validator-webserver\uv.lock","file-validator-core\uv.lock","uv.lock"

Write-Host "Running 'uv sync' (requires 'uv' on PATH)..."
uv sync

Write-Host "Running quick import check inside uv isolated environment..."
uv run python - <<'PY'
import importlib
spec = importlib.util.find_spec('file_validator')
print('file_validator importable:', spec is not None)
if spec:
    import file_validator
    print('file_validator package file:', getattr(file_validator, '__file__', '<unknown>'))
PY

Write-Host "Done. If import still fails, run 'uv sync -v' and paste the output for further triage."
