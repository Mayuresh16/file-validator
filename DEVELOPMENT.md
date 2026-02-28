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

- Runs `uv sync --force -v` to re-evaluate workspace and regenerate locks.
- Checks whether `file_validator` can be imported inside the uv isolated Python.
- If not importable, installs `file-validator-core` into uv's environment as editable (`pip install -e` inside uv env).
- Starts the FastAPI UI with `uv run fastapi run file_validator_webserver.main:app`.

Why this is necessary

- Some build backends or stale lock/egg-info metadata can prevent `uv` from automatically linking a local workspace
  package into the isolated environment. The script provides a safe fallback to ensure local development works reliably
  across machines.

Troubleshooting

- If `uv sync` errors: run `uv sync --force -v` manually and inspect the output. Paste it to the maintainer if needed.
- If editable install fails: run `uv run python -m pip install -e file-validator-core` manually and paste the pip output
  for diagnosis.

Notes

- These scripts are safe for development. For CI, prefer `uv sync` + `uv run pytest` in your pipeline. The editable
  fallback is a developer convenience.

