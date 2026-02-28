#!/usr/bin/env bash
# Start the File Validator UI in a reproducible way.
# Optimized to avoid rebuilding third-party packages on each start:
# - Only run `uv sync` when pyproject.toml changed (tracked via a small hash file)
# - If not changed, skip sync and reuse existing .venv and installed packages
# - If core package missing, install editable fallback into uv env

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

TOOLS_DIR="$REPO_ROOT/.tools"
PYPROJECT="$REPO_ROOT/pyproject.toml"
HASH_FILE="$TOOLS_DIR/pyproject.hash"

mkdir -p "$TOOLS_DIR"

echo "Repo root: $REPO_ROOT"

# Compute current hash of pyproject.toml
if command -v sha1sum >/dev/null 2>&1; then
  CUR_HASH=$(sha1sum "$PYPROJECT" | awk '{print $1}')
else
  # Fallback for environments without sha1sum (e.g., some Windows shells)
  CUR_HASH=$(python -c "import hashlib,sys;print(hashlib.sha1(open('$PYPROJECT','rb').read()).hexdigest())")
fi

# Allow forcing sync via environment variable
FORCE_SYNC=${FORCE_SYNC:-0}

if [ "$FORCE_SYNC" = "1" ] || [ ! -f "$HASH_FILE" ] || [ "$(cat "$HASH_FILE")" != "$CUR_HASH" ]; then
  echo "pyproject.toml changed or no previous sync recorded; running uv sync -v"
  # Remove stale locks so uv will regenerate workspace metadata
  if [ -f "uv.lock" ]; then
    echo "Removing top-level uv.lock (stale)"
    rm -f uv.lock || true
  fi
  if [ -f "file-validator-webserver/uv.lock" ]; then
    echo "Removing file-validator-webserver/uv.lock (stale)"
    rm -f file-validator-webserver/uv.lock || true
  fi
  if [ -f "file-validator-core/uv.lock" ]; then
    echo "Removing file-validator-core/uv.lock (stale)"
    rm -f file-validator-core/uv.lock || true
  fi

  echo "Running: uv sync -v"
  uv sync -v

  # store the new hash
  echo "$CUR_HASH" > "$HASH_FILE"
else
  echo "pyproject.toml unchanged since last sync; skipping 'uv sync' and reusing existing environment"
fi

# Test importability inside uv env
echo "Checking if 'file_validator' is importable inside uv isolated env..."
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
if uv run python -m pip show file-validator-core >/dev/null 2>&1; then
  echo "file-validator-core is installed in uv env"
else
  echo "file-validator-core not installed in uv env"
  # Ensure pip exists in the uv env; if not, bootstrap it via ensurepip
  if ! uv run python -m pip --version >/dev/null 2>&1; then
    echo "pip not found in uv env — bootstrapping ensurepip..."
    uv run python -m ensurepip --upgrade || true
    echo "Upgrading pip/setuptools/wheel inside uv env..."
    uv run python -m pip install --upgrade pip setuptools wheel || true
  fi

  echo "Installing file-validator-core editable into uv env..."
  if ! uv run python -m pip install -e file-validator-core; then
    echo "Editable install failed; retrying with verbose output"
    uv run python -m pip install -e file-validator-core -vvv || true
  fi
fi

# Verify import again after potential install
echo "Verifying import after install..."
uv run python - <<'PY'
import sys, traceback
try:
    import file_validator
    print('file_validator importable: True')
    print('file_validator __file__:', getattr(file_validator, '__file__', '<unknown>'))
except Exception:
    print('file_validator importable: False')
    traceback.print_exc()
PY

# Ensure UI package is importable (so module:app works)
echo "Checking if 'file_validator_webserver' package is importable inside uv env..."
if uv run python - <<'PY' 2>/dev/null | grep -q True; then
  echo "file_validator_webserver importable"
else
  echo "file_validator_webserver not importable; attempting editable install of file-validator-webserver into uv env"
  if uv run python -m pip install -e file-validator-webserver; then
    echo "Installed file-validator-webserver editable into uv env"
  else
    echo "Editable install of file-validator-webserver failed; will fall back to launching uvicorn with --app-dir"
  fi
fi

# Start FastAPI via uv's run (module:app form)
echo "Starting FastAPI: try FastAPI CLI, fall back to uvicorn if necessary"
# Run the server from the UI project folder so uv picks up the ui pyproject
pushd "$REPO_ROOT/file-validator-webserver" >/dev/null || true
# Try FastAPI CLI first (quote the APP to avoid shell/arg parsing issues)
if uv run fastapi run "file_validator_webserver.main:app" --reload --host 127.0.0.1 --port 8000; then
  echo "FastAPI CLI started the app successfully"
else
  echo "FastAPI CLI failed or returned non-zero; falling back to uvicorn via uv run python -m uvicorn"
  # If UI package still isn't importable, pass --app-dir to uvicorn pointing to src folder
  if uv run python - <<'PY' 2>/dev/null | grep -q True; then
    uv run python -m uvicorn file_validator_webserver.main:app --reload --host 127.0.0.1 --port 8000
  else
    echo "file_validator_webserver module still not importable; launching uvicorn with --app-dir file-validator-webserver/src"
    uv run python -m uvicorn file_validator_webserver.main:app --app-dir "$REPO_ROOT/file-validator-webserver/src" --reload --host 127.0.0.1 --port 8000
  fi
fi
popd >/dev/null || true
