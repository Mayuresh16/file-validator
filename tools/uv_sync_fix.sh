#!/usr/bin/env bash
# Helper script to clean stale build/metadata artifacts and re-sync the uv workspace.
# Run this from the repository root (the script will cd there if run from anywhere).

set -euo pipefail

# Compute repo root (directory containing this script's parent 'tools' folder)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "Repo root: $REPO_ROOT"

# Safety: confirm we're in the expected repo
if [ ! -f "pyproject.toml" ]; then
  echo "ERROR: pyproject.toml not found in repo root ($REPO_ROOT). Run this script from inside the repository." >&2
  exit 2
fi

echo "Cleaning stale build/egg-info artifacts..."
# Remove common build/egg-info folders for both packages
rm -rf file-validator-webserver/src/file_validator_webserver.egg-info || true
rm -rf file-validator-core/src/file_validator.egg-info || true
rm -rf file-validator-webserver/build file-validator-webserver/dist || true
rm -rf file-validator-core/build file-validator-core/dist || true

# Remove package-level uv.lock files so uv can regenerate them
rm -f file-validator-webserver/uv.lock || true
rm -f file-validator-core/uv.lock || true

# Also remove any top-level package lock in case it's stale (safe no-op)
rm -f uv.lock || true

echo "Running 'uv sync' to link workspace packages and regen locks..."
# Run uv sync; this requires 'uv' on PATH and should be run from repo root
uv sync

echo "Quick runtime import check using uv-run isolated environment..."
# This runs a tiny Python snippet inside the uv environment to confirm importability
uv run python - <<'PY'
import sys, traceback
try:
    import file_validator
    print('file_validator importable: True')
    print('file_validator __file__:', getattr(file_validator, '__file__', '<unknown>'))
except Exception:
    print('file_validator importable: False')
    traceback.print_exc()
print('\n--- sys.path inside uv isolated env ---')
for p in sys.path:
    print(p)
PY

# Show whether the workspace package is installed in the uv env
echo "\nChecking whether 'file-validator-core' distribution is installed in the uv env..."
uv run python -m pip show file-validator-core || echo "file-validator-core not installed in uv env"

echo "\nIf 'file-validator-core' is not installed in the uv env, you can try this fallback (runs inside the uv env):"
echo "  uv run python -m pip install -e file-validator-core"

echo "Done. If import still fails, please paste the output shown above and the output of 'uv sync -v' for further triage."
