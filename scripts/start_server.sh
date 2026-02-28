#! /bin/bash

ENV=$(echo "${1:-dev}" | tr '[:upper:]' '[:lower:]')

echo "================================"
echo "Synchronizing dependencies..."
uv sync
echo "================================"
echo "Starting server in '$ENV' environment..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Get the repository root (parent of scripts directory)
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Script directory: $SCRIPT_DIR"
echo "Repository root: $REPO_ROOT"
echo "Current working directory: $(pwd)"

# Set PYTHONPATH to include src directories from both packages
export PYTHONPATH="$PYTHONPATH:$REPO_ROOT/file-validator-core/src:$REPO_ROOT/file-validator-webserver/src"
echo "PYTHONPATH: $PYTHONPATH"

if [ "$ENV" = "dev" ]; then
  echo "Running in development mode..."
  uv run fastapi dev "$REPO_ROOT/file-validator-webserver/src/file_validator_webserver/main.py" \
    --app app \
    --host 127.0.0.1 \
    --port 9000

elif [ "$ENV" = "prod" ]; then
  echo "Running in production mode..."
  uv run fastapi run "$REPO_ROOT/file-validator-webserver/src/file_validator_webserver/main.py" \
    --app app \
    --host 127.0.0.1 \
    --port 9290
fi

echo "================================"
echo "Server stopped."
echo "================================"
