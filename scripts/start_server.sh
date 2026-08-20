#! /bin/bash

# Script name for help messages
SCRIPT_NAME="$0"

# Default values
ENV="prod"
PORT=""
HOST=""

# Function to display help message
show_help() {
  echo "Usage: $SCRIPT_NAME [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  -e, --env ENV     Environment to run (dev|prod, default: prod)"
  echo "  -p, --port PORT   Port to run on (default: 9000 for dev, 9290 for prod)"
  echo "  -h, --host HOST   Host address to bind (default: 127.0.0.1 for dev, required for prod)"
  echo "      --help        Show this help message"
  echo ""
  echo "Examples:"
  echo "  $SCRIPT_NAME -e dev"
  echo "  $SCRIPT_NAME --env=prod -h 0.0.0.0 --port=8080"
  echo "  $SCRIPT_NAME -e dev -p 9000 -h localhost"
}

# Function to parse and validate CLI arguments
parse_cli_arguments() {
  while [[ $# -gt 0 ]]; do
    case $1 in
      -e=*|--env=*)
        ENV="${1#*=}"
        shift
        ;;
      -e|--env)
        ENV="$2"
        shift 2
        ;;
      -p=*|--port=*)
        PORT="${1#*=}"
        shift
        ;;
      -p|--port)
        PORT="$2"
        shift 2
        ;;
      -h=*|--host=*)
        HOST="${1#*=}"
        shift
        ;;
      -h|--host)
        HOST="$2"
        shift 2
        ;;
      --help)
        show_help
        exit 0
        ;;
      *)
        echo "Error: Unknown option '$1'"
        echo "Run '$SCRIPT_NAME --help' for usage information"
        exit 1
        ;;
    esac
  done

  # Normalize and validate environment
  ENV=$(echo "$ENV" | tr '[:upper:]' '[:lower:]')
  [[ ! "$ENV" =~ ^(dev|prod)$ ]] && { echo "Error: Invalid environment '$ENV'. Must be 'dev' or 'prod'."; exit 1; }

  # Validate port if provided
  [[ -n "$PORT" && ! "$PORT" =~ ^[0-9]+$ ]] && { echo "Error: Port must be a numeric value, got '$PORT'"; exit 1; }

  # Validate host for production environment
  [[ "$ENV" == "prod" && -z "$HOST" ]] && { 
    echo "Error: Host must be specified for production environment"; 
    echo "Use -h or --host to specify the host address"; 
    exit 1; 
  }
}

# Parse command line arguments
parse_cli_arguments "$@"

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

# Set default port based on environment if not specified
if [[ -z "$PORT" ]]; then
  if [ "$ENV" = "dev" ]; then
    PORT=9000
  else
    PORT=9290
  fi
fi

# Set default host for dev environment if not specified
if [[ -z "$HOST" && "$ENV" = "dev" ]]; then
  HOST="127.0.0.1"
fi

echo "Host: $HOST"
echo "Port: $PORT"

if [ "$ENV" = "dev" ]; then
  echo "Running in development mode..."
  uv run fastapi dev "$REPO_ROOT/file-validator-webserver/src/file_validator_webserver/main.py" \
    --app app \
    --host "$HOST" \
    --port "$PORT"

elif [ "$ENV" = "prod" ]; then
  echo "Running in production mode..."
  uv run fastapi run "$REPO_ROOT/file-validator-webserver/src/file_validator_webserver/main.py" \
    --app app \
    --host "$HOST" \
    --port "$PORT"
fi

echo "================================"
echo "Server stopped."
echo "================================"
