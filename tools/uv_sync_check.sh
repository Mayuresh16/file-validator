#!/usr/bin/env bash
set -euo pipefail

echo "Running uv sync -v..."
uv sync -v

echo
echo "Checking importability inside the uv environment..."
uv run python - <<'PY'
import importlib, importlib.util, sys

print('Python executable:', sys.executable)
print('--- sys.path (first 10 entries) ---')
for p in sys.path[:10]:
    print(' ', p)

for pkg in ('file_validator', 'file_validator_webserver'):
    spec = importlib.util.find_spec(pkg)
    print(f"find_spec('{pkg}') ->", spec)
    try:
        m = importlib.import_module(pkg)
        print(f"import {pkg}: OK ->", getattr(m, '__file__', None))
    except Exception as e:
        print(f"import {pkg}: ERR ->", e)

PY

echo
echo "Try running the FastAPI app using the uv fastapi runner (example):"
echo "  uv run fastapi run -e file_validator_webserver.main:app --no-reload --port 9876"

echo "Done."

