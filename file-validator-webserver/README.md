# File Validator WebServer

**Version:** 1.0  
**Last Updated:** February 01, 2026=

A user-friendly FastAPI web application for file validation, providing a modern UI to configure and run validation jobs
with real-time progress updates.

---

## 📚 Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Configuration Options](#configuration-options)
6. [Project Structure](#project-structure)
7. [API Endpoints](#api-endpoints)
8. [Web Interface](#web-interface)
9. [Job Management](#job-management)
10. [Integration](#integration)
11. [Troubleshooting](#troubleshooting)
12. [Development](#development)

---

## Overview

File Validator WebServer provides a professional web interface for the file-validator-core library. Built with FastAPI,
it offers:

- **Modern, responsive UI** matching the file_validator report style
- **Async job processing** for non-blocking validation
- **Real-time status updates** via polling
- **Job history tracking** (browser-based)
- **Full GCS support** with OAuth2 authentication
- **Compression handling** for .gz, .Z, .bz2, .zip files

---

## Features

- 📊 **Professional UI** — Modern, responsive design with dark mode
- 🌙 **Dark Mode** — Toggle between light and dark themes with persistence
- ⚡ **Async Processing** — Background job processing via `ThreadPoolExecutor`
- 📈 **Live Status Updates** — Real-time polling with progress bar
- 📄 **Report Generation** — Interactive HTML reports
- 📊 **Excel Export** — On-demand multi-sheet workbooks streamed to client
- 📜 **Job History** — Recent jobs stored in browser localStorage
- 🗂️ **GCS Support** — Read files directly from `gs://` URIs
- 📦 **Compression Support** — .gz, .Z, .bz2, .zip handled automatically
- 🔐 **OAuth2 / OIDC** — Automatic token refresh for GCS access
- 🚀 **High Performance** — `ThreadPoolExecutor` with auto-scaled workers
- 📱 **Responsive Design** — Works on desktop, tablet, and mobile

---

## Installation

### Prerequisites

- Python 3.13+
- UV package manager (recommended)
- file-validator-core package (workspace dependency)

### Setup

```bash
# From repository root (installs both packages)
uv sync

# Or install individually
cd file-validator-webserver
uv pip install -e .
```

---

## Usage

### Running the App

From the `file-validator` repository root:

```bash
# Option 1: Using start script (recommended)
bash scripts/start_server.sh [dev/prod]       # Bash - default dev server
./scripts/start_server.ps1   [dev/prod]       # PowerShell - default dev server

# Option 2: FastAPI dev server (auto-reload)
uv run fastapi dev src/file_validator_webserver/main.py

# Option 3: Uvicorn directly
uvicorn file_validator_webserver.main:app --reload

# Option 4: Production
uvicorn file_validator_webserver.main:app --host 0.0.0.0 --port 8000
```

Then open http://127.0.0.1:8000 in your browser.

### Custom Port

```bash
uvicorn file_validator_webserver.main:app --port 8001
```

---

## Configuration Options

Configure validation jobs through the web form:

| Field                | Description                                                        | Default  |
|----------------------|--------------------------------------------------------------------|----------|
| Job Name             | Logical name used in the job ID                                    | Required |
| Source File Path     | Local path or GCS URI (`gs://bucket/path`)                         | Required |
| Target File Path     | Local path or GCS URI (`gs://bucket/path`)                         | Required |
| Primary Keys         | List of column names for row matching (comma seperated through UI) | Required |
| Delimiter            | Field delimiter character                                          | `,`      |
| Header Rows          | Number of header rows to skip                                      | `0`      |
| File Type            | `csv`, `psv` (pipe-separated), or `fwf` (fixed-width)              | `csv`    |
| Column Specification | FWF column widths (e.g. `10,5,8`)                                  | Optional |
| Trailer Patterns     | Patterns that identify trailer rows                                | Optional |
| Encoding             | File encoding                                                      | `utf-8`  |
| Compression          | `auto`, `gzip`, `compress`, `bzip2`, `zip`, or `None`              | `auto`   |

### Example Configurations

**Basic CSV Comparison:**

```
Job Name:     daily_check
Source Path:  data/source.csv
Target Path:  data/target.csv
Primary Keys: id, date
Delimiter:    ,
Header Rows:  1
```

**GCS with Compression:**

```
Source Path: gs://my-bucket/data/source.csv.gz
Target Path: gs://my-bucket/data/target.csv.gz
Primary Keys: customer_id
Compression: auto
```

**Pipe-Separated Values:**

```
Source Path: data/source.psv
Target Path: data/target.psv
Primary Keys: account_number
Delimiter:   |
File Type:   psv
```

**Fixed-Width (FWF):**

```
Source Path:          data/source.txt
Target Path:          data/target.txt
File Type:            fwf
Column Specification: 10,10,8,6    ← column widths, not ranges
Header Rows:          1
```

---

## Project Structure

```
file-validator-webserver/
├── pyproject.toml
├── README.md
├── src/
│   └── file_validator_webserver/
│       ├── __init__.py
│       ├── main.py             # FastAPI app, routes, job runner
│       ├── fs_utils.py         # Async filesystem utilities
│       ├── templates/
│       │   └── index.html      # Main UI template
│       ├── static/
│       │   ├── style.css
│       │   └── favicon.svg
│       └── uploads/            # Temporary uploaded files
└── tests/
    └── test_sample.py
```

### Key Files

| File          | Purpose                                                                                                  |
|---------------|----------------------------------------------------------------------------------------------------------|
| `main.py`     | FastAPI app, all API routes, background job runner, cache management                                     |
| `fs_utils.py` | Async wrappers: `async_path_exists`, `async_list_files`, `async_resolve`, `async_unlink`, `async_rmtree` |
| `index.html`  | Web UI — form, job status display, job history                                                           |
| `style.css`   | Custom CSS for UI styling                                                                                |

---

## API Endpoints

### REST API

| Endpoint                 | Method | Description                                  |
|--------------------------|--------|----------------------------------------------|
| `/`                      | GET    | Main UI page (HTML)                          |
| `/validate`              | POST   | Start a validation job                       |
| `/upload`                | POST   | Upload a local file to the server            |
| `/status/{job_id}`       | GET    | Get job status and progress                  |
| `/report/{job_id}`       | GET    | Download HTML report as file attachment      |
| `/report/{job_id}/view`  | GET    | View HTML report inline (iframe-friendly)    |
| `/report/{job_id}/excel` | GET    | Generate and download Excel report on-demand |
| `/cache/stats`           | GET    | Return on-disk result cache statistics       |

---

### POST /validate

Starts a validation job in the background. Returns immediately with the `job_id`.

**Request body (`application/json`):**

```json
{
  "job_name": "daily_reconciliation",
  "source_path": "data/source.csv",
  "source_filename": "source.csv",
  "target_path": "data/target.csv",
  "target_filename": "target.csv",
  "primary_keys": [
    "id",
    "date"
  ],
  "delimiter": ",",
  "header_rows": 1,
  "file_type": "csv",
  "trailer_patterns": [
    "TRAILER",
    "TOTAL"
  ],
  "encoding": "utf-8",
  "compression": "auto",
  "column_specification": null,
  "normalization": {
    "normalization": [
      "trim"
    ],
    "normalize_dates": false,
    "treat_null_as_empty": true,
    "float_epsilon": null,
    "ltrim_columns": [],
    "rtrim_columns": [],
    "trim_columns": []
  }
}
```

> **`primary_keys`** must be a JSON array of strings, not a comma-separated string.

**Response:**

```json
{
  "job_id": "daily_reconciliation_source_20260228_143022",
  "status": "started"
}
```

**Job ID format:** `<job_name>_<source_stem>_<YYYYMMDD_HHMMSS>`

---

### POST /upload

Upload a local file to the server's `uploads/` directory.

**Request:** multipart form with a `file` field.

**Response:**

```json
{
  "success": true,
  "path": "/absolute/path/to/uploads/20260228_143022_source.csv",
  "filename": "source.csv"
}
```

Use the returned `path` value as `source_path` or `target_path` in `/validate`.

---

### GET /status/{job_id}

**Response (running):**

```json
{
  "job_id": "daily_reconciliation_source_20260228_143022",
  "status": "running",
  "progress": 50,
  "message": "Running comparison...",
  "result": null
}
```

**Response (completed):**

```json
{
  "job_id": "daily_reconciliation_source_20260228_143022",
  "status": "completed",
  "progress": 100,
  "message": "Completed in 1 min 23 sec",
  "result": {
    "html_report": "/abs/path/reports/daily_reconciliation_source_20260228_143022_report.html",
    "summary": {
      "source_count": 10000,
      "target_count": 10000,
      "matching_rows": 9500,
      "mismatched_rows": 400,
      "missing_in_source": 50,
      "missing_in_target": 50,
      "match_percentage": 95.0,
      "row_count_diff": 0
    }
  }
}
```

**Status values:** `pending` → `running` → `completed` | `error`

**Progress milestones:**

| %   | Phase                                    |
|-----|------------------------------------------|
| 5   | Initializing configuration               |
| 10  | Configuration initialized                |
| 15  | Creating file auditor                    |
| 20  | Loading source file                      |
| 40  | Data loaded                              |
| 50  | Running comparison                       |
| 70  | Comparison completed                     |
| 75  | Generating sample data (100% match only) |
| 80  | Generating HTML report                   |
| 90  | Report generated                         |
| 95  | Cleaning up resources                    |
| 100 | Complete                                 |

---

### GET /report/{job_id}

Downloads the HTML report as a file attachment (`{job_id}_report.html`).

---

### GET /report/{job_id}/view

Returns the HTML report inline — suitable for embedding in an `<iframe>`.

---

### GET /report/{job_id}/excel

Generates the Excel workbook on-demand and streams it to the client
(`{job_id}_report.xlsx`). The `.xlsx` and parquet cache files are deleted
from disk once the download completes (via a background cleanup task).

> Requires the job to be in `completed` status and the result cache to still
> be present (cache TTL is **1 hour**; entries are cleaned up every 10 minutes).

---

### GET /cache/stats

Returns statistics about the on-disk result cache directory (`reports/_cache/`).

**Response:**

```json
{
  "files": 3,
  "total_bytes": 524288,
  "oldest_mtime": 1740740400.0,
  "newest_mtime": 1740744000.0
}
```

---

## Web Interface

### Main Features

#### 1. Job Configuration Form

- **File paths**: local paths or `gs://` URIs
- **File upload**: drag-and-drop or browse to upload local files
- **File type**: CSV, PSV, FWF with appropriate sub-options
- **FWF support**: column widths field (e.g. `10,5,8`)
- **Normalization**: trim, date normalization, null handling, column-specific rules
- **Advanced options**: encoding, compression, trailer patterns

#### 2. Job Status Display

- **Progress bar** with percentage and phase message
- **Elapsed time** shown on completion
- **Summary statistics** table after completion
- **Report action buttons**: Download HTML, Download Excel, View inline

#### 3. Job History

- Last jobs stored in browser `localStorage`
- Quick links back to reports for previous runs
- Status badges and timestamps

### UI Layout

```
┌─────────────────────────────────────────────┐
│  File Validator                    [Theme]  │
├─────────────────────────────────────────────┤
│  Job Name:         ____________________     │
│  Source File Path: ____________________     │
│  Target File Path: ____________________     │
│  Primary Keys:     ____________________     │
│                                             │
│  ▼ Advanced Options                         │
│     Delimiter:        [,]                   │
│     Header Rows:      [0]                   │
│     File Type:        [CSV ▼]               │
│     Trailer Patterns: ______________        │
│     Normalization:    [None ▼]              │
│                                             │
│              [Submit Validation]            │
│                                             │
├─────────────────────────────────────────────┤
│  Job Status                                 │
│  ⚡ Running... (50%)                        │
│  Progress: ████████░░░░                     │
│                                             │
├─────────────────────────────────────────────┤
│  Recent Jobs                                │
│  ✓ daily_rec_source_20260228 - 95% - 2m ago │
│  ✓ nightly_file_20260227 - 100% - 1h ago   │
│  ✗ batch_run_20260226 - Error - 3h ago     │
└─────────────────────────────────────────────┘
```

---

## Job Management

### Job Lifecycle

```
User Submits Form
       ↓
Generate Job ID: <job_name>_<source_stem>_<YYYYMMDD_HHMMSS>
       ↓
Store initial state in job_store (in-memory)
       ↓
Dispatch to ThreadPoolExecutor (non-blocking)
       ↓
Return {"job_id": ..., "status": "started"}
       ↓
Client polls GET /status/{job_id}
       ↓
Background: Initialize → Load → Compare → Report
       ↓
Persist results + sample as Parquet to reports/_cache/
       ↓
Update job_store: status="completed", result={...}
       ↓
Client downloads HTML/Excel reports
       ↓
Excel download triggers cache cleanup
```

### Storage Locations

| Path              | Contents                              | Lifecycle                                          |
|-------------------|---------------------------------------|----------------------------------------------------|
| `reports/`        | HTML reports (`{job_id}_report.html`) | Retained until manual cleanup                      |
| `reports/_cache/` | Parquet artifacts for Excel export    | 1-hour TTL; swept every 10 min; purged on shutdown |
| `uploads/`        | Uploaded source/target files          | Deleted on server shutdown                         |
| `logs/webserver/` | Timestamped rotating log files        | Manual cleanup                                     |

### Background Processing

- Jobs run inside a `ThreadPoolExecutor` (`max_workers=max(cpu_count, 4)`)
- Each job is fully isolated — resources cleaned up via `FileAuditor` context manager
- Stale `duckdb_work_*` and `file_validator_*` temp directories from crashed runs are swept on startup and shutdown

---

## Integration

### With file-validator-core

The server uses the core package for all validation logic:

```python
from file_validator.auditor import FileAuditor
from file_validator.config import FileConfig, NormalizationConfig
from file_validator.report_generator import generate_html_report
from file_validator.excel_exporter import build_and_save_excel_file
```

**Workflow:**

```python
with FileAuditor(
        source_config=source_conf,
        target_config=target_conf,
        primary_keys=config.primary_keys,
        norm_config=config.normalization,
) as auditor:
    auditor.load_data()
    results = auditor.run_comparison()
    sample_df = auditor.get_sample_data() if results.is_empty() else None
    generate_html_report(df=results, ...)
```

### API Client Integration

```python
import requests
import time

BASE = "http://localhost:8000"

# 1. (Optional) Upload local files
with open("source.csv", "rb") as f:
    src = requests.post(f"{BASE}/upload", files={"file": f}).json()
with open("target.csv", "rb") as f:
    tgt = requests.post(f"{BASE}/upload", files={"file": f}).json()

# 2. Start validation
resp = requests.post(f"{BASE}/validate", json={
    "job_name": "daily_check",
    "source_path": src["path"],
    "source_filename": src["filename"],
    "target_path": tgt["path"],
    "target_filename": tgt["filename"],
    "primary_keys": ["id", "date"],
    "delimiter": ",",
    "header_rows": 1,
    "file_type": "csv",
})
job_id = resp.json()["job_id"]

# 3. Poll for completion
while True:
    status = requests.get(f"{BASE}/status/{job_id}").json()
    print(f"[{status['progress']}%] {status['message']}")
    if status["status"] in ("completed", "error"):
        break
    time.sleep(2)

# 4. Download HTML report
if status["status"] == "completed":
    report = requests.get(f"{BASE}/report/{job_id}")
    with open("report.html", "wb") as f:
        f.write(report.content)

    # 5. Download Excel report
    excel = requests.get(f"{BASE}/report/{job_id}/excel")
    with open("report.xlsx", "wb") as f:
        f.write(excel.content)

    # 6. Print summary
    summary = status["result"]["summary"]
    print(f"Match %: {summary['match_percentage']:.2f}%")
    print(f"Matched: {summary['matching_rows']:,}")
    print(f"Mismatch: {summary['mismatched_rows']:,}")
```

---

## Troubleshooting

### Common Issues

#### Port Already in Use

```bash
# Linux/Mac
lsof -i :8000

# Windows
netstat -ano | findstr :8000

# Use a different port
uvicorn file_validator_webserver.main:app --port 8001
```

#### Import Errors

```bash
# Ensure workspace packages are linked
uv sync --force

# Or install core manually
uv pip install -e ../file-validator-core
```

#### GCS Authentication

```bash
# Service account key
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"

# Or use gcloud ADC
gcloud auth application-default login

# Verify
python -c "from google.auth import default; creds, p = default(); print(p)"
```

#### Memory Errors on Large Files

Use the DuckDB env vars — no code changes needed:

```bash
# In configs/.env or shell before starting the server
export DUCKDB_MEMORY_LIMIT="16GB"
export DUCKDB_ALLOCATOR_FLUSH_THRESHOLD="512MB"
```

Or pass the parameter when constructing `FileAuditor` directly (advanced usage):

```python
FileAuditor(source, target, primary_keys=["id"], memory_limit="16GB", threads=8)
```

See the [file-validator-core DuckDB Tuning section](../file-validator-core/README.md#duckdb-tuning)
for the full list of tunable env vars.

#### Excel Download Returns 404

The Excel endpoint requires:

1. The job status to be `completed`
2. The Parquet cache files to still exist (TTL = **1 hour**)

If the cache has expired, re-run the validation job.

#### File Upload Issues

```bash
# Check uploads directory permissions
ls -la src/file_validator_webserver/uploads/

# Create if missing
mkdir -p src/file_validator_webserver/uploads
```

### Debug Logging

```python
# In main.py, change log level to DEBUG
setup_logging(log_level="DEBUG", log_file="logs/webserver/debug.log")
```

```bash
# Tail the latest log
ls -t logs/webserver/ | head -1 | xargs -I{} tail -f logs/webserver/{}
```

---

## Development

### Running Tests

```bash
# From repository root
uv run pytest file-validator-webserver/tests/

# With coverage
uv run pytest --cov=file_validator_webserver file-validator-webserver/tests/

# Verbose
uv run pytest -v file-validator-webserver/tests/
```

### Development Server

```bash
# Auto-reload on code changes
uvicorn file_validator_webserver.main:app --reload

# Or with FastAPI CLI
fastapi dev src/file_validator_webserver/main.py

# Or using start script
bash scripts/start_server.sh
```

### Building for Production

```bash
cd file-validator-webserver
uv build
```

Production deployment with Gunicorn:

```bash
gunicorn file_validator_webserver.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 300
```

### Code Quality

```bash
uv run ruff check src/
uv run ruff format src/
uv run mypy src/
```

---

## Performance

### Benchmarks

Typical performance on modern hardware (file load + comparison + HTML report):

| File Size | Rows | Total Time   |
|-----------|------|--------------|
| 10 MB     | 100K | ~3 seconds   |
| 100 MB    | 1M   | ~17 seconds  |
| 1 GB      | 10M  | ~2.5 minutes |

### Optimization Tips

1. **Use GCS compression** — `.gz` reduces transfer time
2. **Tune DuckDB** — set `DUCKDB_MEMORY_LIMIT` for large files
3. **Increase threads** — `FileAuditor(threads=8)` for larger files
4. **Scale workers** — run multiple Uvicorn workers for concurrent jobs

---

## Dependencies

- **`fastapi[standard]>=0.129.0`** — async web framework
- **`uvicorn`** — ASGI server (bundled with `fastapi[standard]`)
- **`pydantic`** — request/response validation
- **`jinja2`** — HTML template rendering
- **`aiofiles>=25.1.0`** — async file I/O
- **`polars>=1.38.1`** — high-performance DataFrames (via `file-validator-core`)
- **`python-dotenv>=1.2.1`** — `.env` loading (via `file-validator-core`)
- **`file-validator-core`** — core validation engine (workspace dependency)

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Author

**Mayuresh Kedari**   <mayurkedari16@gmail.com>

---

## See Also

- [File Validator Core](../file-validator-core/README.md) — Core library documentation
- [Main README](../README.md) — Project overview
- [DEVELOPMENT.md](../../DEVELOPMENT.md) — Development guide
