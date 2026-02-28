<#
PowerShell helper to start the File Validator UI reliably.
Performs uv sync --force, checks importability, installs editable fallback if needed, and launches the UI.
#>
param()

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path "$scriptDir\.."
Set-Location $repoRoot

Write-Host "Repo root: $repoRoot"

# Optimize: only run `uv sync` when pyproject.toml changes
$toolsDir = Join-Path $repoRoot ".tools"
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
$pyproject = Join-Path $repoRoot "pyproject.toml"
$hashFile = Join-Path $toolsDir "pyproject.hash"

# compute current SHA1 hash
try {
    $curHash = (Get-FileHash -Path $pyproject -Algorithm SHA1).Hash
} catch {
    Write-Error "Failed to compute hash of $pyproject: $_"
    exit 1
}

$forceSync = $env:FORCE_SYNC -eq '1'
$needSync = $false
if ($forceSync -or -not (Test-Path $hashFile)) {
    $needSync = $true
} else {
    $prev = Get-Content $hashFile -ErrorAction SilentlyContinue
    if ($prev -ne $curHash) { $needSync = $true }
}

if ($needSync) {
    Write-Host "pyproject.toml changed or no previous sync recorded; running uv sync -v"
    # Remove stale locks so uv will regenerate workspace metadata
    if (Test-Path "uv.lock") {
        Write-Host "Removing top-level uv.lock (stale)"
        Remove-Item -Force "uv.lock" -ErrorAction SilentlyContinue
    }
    if (Test-Path "file-validator-webserver\uv.lock") {
        Write-Host "Removing file-validator-webserver\uv.lock (stale)"
        Remove-Item -Force "file-validator-webserver\uv.lock" -ErrorAction SilentlyContinue
    }
    if (Test-Path "file-validator-core\uv.lock") {
        Write-Host "Removing file-validator-core\uv.lock (stale)"
        Remove-Item -Force "file-validator-core\uv.lock" -ErrorAction SilentlyContinue
    }

    Write-Host "Running: uv sync -v"
    uv sync -v

    # save hash
    Set-Content -Path $hashFile -Value $curHash
} else {
    Write-Host "pyproject.toml unchanged since last sync; skipping 'uv sync' and reusing existing environment"
}

Write-Host "Checking if 'file_validator' is importable inside uv isolated env..."
$importOk = uv run python -c "import file_validator; print('IMPORT_OK')" 2>$null | Select-String IMPORT_OK
if ($importOk) {
    Write-Host "file_validator is importable in uv env"
} else {
    Write-Host "file_validator NOT importable in uv env; installing editable fallback"
    uv run python -m pip install -e file-validator-core
    Write-Host "Installed file-validator-core editable into uv env"
}

Write-Host "Checking if 'file_validator_webserver' package is importable inside uv env..."
$uiImport = uv run python -c "import importlib,sys; print(importlib.util.find_spec('file_validator_webserver') is not None)" 2>$null
if ($uiImport -and $uiImport.ToString().Trim() -eq 'True') {
    Write-Host "file_validator_webserver importable"
} else {
    Write-Host "file_validator_webserver not importable; attempting editable install of file-validator-webserver into uv env"
    try {
        uv run python -m pip install -e file-validator-webserver
        Write-Host "Installed file-validator-webserver editable into uv env"
    } catch {
        Write-Host "Editable install of file-validator-webserver failed; will fall back to launching uvicorn with --app-dir"
    }
}

Write-Host "Starting FastAPI: try FastAPI CLI, fall back to uvicorn if necessary"
# Try FastAPI CLI first
try {
    & uv run fastapi run "file_validator_webserver.main:app" --reload --host 127.0.0.1 --port 8000
    Write-Host "FastAPI CLI started the app successfully"
    return
} catch {
    Write-Host "FastAPI CLI failed or returned non-zero; falling back to uvicorn via uv run python -m uvicorn"
}

# If UI still not importable, run uvicorn with --app-dir
$uiImport2 = uv run python -c "import importlib,sys; print(importlib.util.find_spec('file_validator_webserver') is not None)" 2>$null
if ($uiImport2 -and $uiImport2.ToString().Trim() -eq 'True') {
    uv run python -m uvicorn file_validator_webserver.main:app --reload --host 127.0.0.1 --port 8000
} else {
    Write-Host "file_validator_webserver module still not importable; launching uvicorn with --app-dir file-validator-webserver/src"
    $appDir = Join-Path $repoRoot 'file-validator-webserver\src'
    uv run python -m uvicorn file_validator_webserver.main:app --app-dir $appDir --reload --host 127.0.0.1 --port 8000
}
