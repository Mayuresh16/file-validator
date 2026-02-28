Developer run instructions

Goal: reliably start the File Validator UI using the project's `uv` workspace runner. These steps ensure the
`file-validator-core` workspace package is linked or installed into the uv isolated environment so the UI can
`import file_validator`.

1) Recommended one-liner (Bash):

```bash
bash scripts/start_server.sh
```

2) Recommended one-liner (PowerShell):

```powershell
./scripts/start_server.ps1
```

What the script does

- Runs `uv sync --reinstall -v` to re-evaluate workspace and regenerate locks.
- Checks whether `file_validator` can be imported inside the uv isolated Python.
- If not importable, installs `file-validator-core` into uv's environment as editable (`pip install -e` inside uv env).
- Starts the FastAPI UI with `uv run fastapi run file_validator_webserver.main:app`.

Why this is necessary

- Some build backends or stale lock/egg-info metadata can prevent `uv` from automatically linking a local workspace
  package into the isolated environment. The script provides a safe fallback to ensure local development works reliably
  across machines.

Troubleshooting

- If `uv sync` errors: run `uv sync --reinstall -v` manually and inspect the output. Paste it to the maintainer if
  needed.
- If editable install fails: run `uv run python -m pip install -e file-validator-core` manually and paste the pip output
  for diagnosis.

Notes

- These scripts are safe for development. For CI, prefer `uv sync` + `uv run pytest` in your pipeline. The editable
  fallback is a developer convenience.

---

## Running Tests

Goal: Execute pytest with workspace dependencies synchronized. The test runner script handles dependency sync and
configures the Python path for both workspace packages.

### Recommended test commands

1) **Bash:**

```bash
# Run all tests
bash scripts/run_tests.sh

# Run only file-validator-core tests
bash scripts/run_tests.sh core

# Run only file-validator-webserver tests
bash scripts/run_tests.sh webserver

# Run all tests with verbose output
bash scripts/run_tests.sh all -v
```

2) **PowerShell:**

```powershell
# Run all tests
./scripts/run_tests.ps1

# Run only file-validator-core tests
./scripts/run_tests.ps1 -TestType core

# Run only file-validator-webserver tests
./scripts/run_tests.ps1 -TestType webserver

# Run all tests with verbose output
./scripts/run_tests.ps1 -TestType all -Verbose
```

### What the test script does

- Runs `uv sync` to synchronize dependencies
- Sets up `PYTHONPATH` to include src directories from both packages
- Executes pytest with appropriate configuration from `pyproject.toml`
- Supports filtering by package (core, webserver, or all)
- Provides verbose output option for detailed test results
- Returns appropriate exit codes for CI/CD integration

### Troubleshooting tests

- If tests fail due to import errors: ensure `PYTHONPATH` includes both package src directories
- If `uv sync` errors: run `uv sync --force -v` manually to diagnose dependency issues
- For isolated test debugging: run `uv run pytest <test_file> -vv` directly
