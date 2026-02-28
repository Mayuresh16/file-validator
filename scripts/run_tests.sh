#!/bin/bash

# Test runner script for file-validator project
# Executes pytest with workspace dependencies synchronized

TEST_TYPE="${1:-all}"
VERBOSE="${2:-}"

echo "================================"
echo "Synchronizing dependencies..."
uv sync
echo "================================"

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

echo "================================"
echo "Running tests..."
echo "================================"

# Build pytest command with optional verbosity flag
PYTEST_CMD="uv run pytest"

if [ ! -z "$VERBOSE" ] && [ "$VERBOSE" = "-v" ]; then
  PYTEST_CMD="$PYTEST_CMD -vv"
fi

case "$TEST_TYPE" in
  core)
    echo "Running file-validator-core tests..."
    $PYTEST_CMD "$REPO_ROOT/file-validator-core/tests" --rootdir="$REPO_ROOT"
    ;;
  webserver)
    echo "Running file-validator-webserver tests..."
    $PYTEST_CMD "$REPO_ROOT/file-validator-webserver/tests" --rootdir="$REPO_ROOT"
    ;;
  all|*)
    echo "Running all tests..."
    $PYTEST_CMD "$REPO_ROOT" --rootdir="$REPO_ROOT"
    ;;
esac

EXIT_CODE=$?

echo "================================"
if [ $EXIT_CODE -eq 0 ]; then
  echo "Tests completed successfully."
else
  echo "Tests failed with exit code: $EXIT_CODE"
fi
echo "================================"

exit $EXIT_CODE

