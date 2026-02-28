# File Validator

**Version:** 2.0 (In Development)  
**Last Updated:** February 28, 2026  
**Status:** Phase 1 Complete ✅

A file validation and comparison framework with interactive reporting and a web UI.

---

## 📚 **PHASE 1 IMPLEMENTATION COMPLETE**

### 👉 **START HERE:**

- **[📖 Documentation README](documentation/README.md)** - Complete documentation index
- **[🚀 Quick Start Guide](documentation/INDEX.md)** - Project overview and structure
- **[✨ Phase 1 Summary](documentation/PHASE1-FINAL-SUMMARY.md)** - What was built

### 📍 **Key Locations:**

- **Implementation:** `src/file_validator/` (unified module with modern Python 3.13+ type hints)
- **Tests:** `tests/` (comprehensive test infrastructure with fixtures)
- **Documentation:** `documentation/` (all planning and implementation guides)

---

---

## Overview

File Validator is a [UV workspace](https://docs.astral.sh/uv/concepts/workspaces/) for validating, comparing, and
auditing data files. It provides:

- **Comparison engine** powered by DuckDB (file-backed, spill-to-disk) and Polars
- **Interactive HTML reports** with dark mode, search, and character-level diff
- **Web UI** (FastAPI) for configuration, job management, and live progress
- **File format support** — CSV, PSV, TSV, custom delimiters, Fixed-Width (FWF)
- **Cloud storage** — Google Cloud Storage (`gs://` URIs) via DuckDB httpfs
- **Compression** — automatic handling of `.gz`, `.Z`, `.bz2`, `.zip`
- **Excel export** — multi-sheet workbooks (openpyxl)
- **DuckDB tuning** — `memory_limit`, `preserve_insertion_order`, and `allocator_flush_threshold` configurable via
  environment variables

---

## <span style="color: red; font-weight: bold;">⚠️ Note:</span>

This project currently focuses on `Local` storage and `GCS` for cloud storage support.

Support for AWS S3 and Azure Blob Storage may be added in the future based on demand.

---

## Project Structure

```
file-validator/
├── file-validator-core/          # Core validation library (Python package)
│   └── src/file_validator/
│       ├── auditor.py            # FileAuditor — DuckDB comparison engine
│       ├── config.py             # FileConfig, NormalizationConfig dataclasses
│       ├── converters.py         # FWF-to-Parquet converter (Polars)
│       ├── credentials.py        # GCS OAuth2/OIDC token management
│       ├── excel_exporter.py     # Multi-sheet Excel export
│       ├── report_generator.py   # HTML report generation (Jinja2)
│       ├── constants.py          # Color constants (StrEnum)
│       ├── exceptions.py         # Custom exceptions (GCSConnectionError)
│       ├── utils.py              # format_bytes, calculate_time, logging setup
│       ├── templates/
│       │   └── html_report.html  # Compiled HTML/CSS/JS report template
│       └── file_handlers/        # File I/O abstraction layer
│           ├── interface.py      # Protocol + ABC base class
│           ├── local_handler.py  # Local filesystem handler
│           ├── gcs_handler.py    # GCS handler (google-cloud-storage)
│           └── compression.py    # Decompression utilities
├── file-validator-webserver/     # FastAPI web interface
│   └── src/file_validator_webserver/
│       ├── main.py               # App, API endpoints, background jobs
│       ├── fs_utils.py           # Async filesystem helpers
│       ├── static/               # CSS, favicon
│       └── templates/            # Jinja2 HTML templates
├── configs/                      # Environment config (.env)
├── logs/                         # Application logs (core/, webserver/)
├── reports/                      # Generated reports + parquet cache (_cache/)
├── scripts/                      # Start scripts and dev utilities
└── pyproject.toml                # Workspace manifest
```

### Workspace Packages / Components

| Package                      | Description                                                                  |
|------------------------------|------------------------------------------------------------------------------|
| **file-validator-core**      | Core library — file comparison, report generation, Excel export, GCS support |
| **file-validator-webserver** | FastAPI web app — async validation jobs, file upload, report serving         |

---

## Installation

### Prerequisites

- **Python 3.13+**
- **[UV](https://docs.astral.sh/uv/)** package manager (recommended)

### Quick Start

```bash
cd file-validator
uv sync
```

### Start the Web UI

```bash
# Bash (recommended — handles sync, checks imports)
bash scripts/start_server.sh

# PowerShell
.\scripts\start_server.ps1

# Direct (dev mode with hot-reload, port 9000)
uv run fastapi dev file-validator-webserver/src/file_validator_webserver/main.py --host 127.0.0.1 --port 9000

# Direct (production mode, port 8000)
uv run fastapi run file-validator-webserver/src/file_validator_webserver/main.py --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 (or `:9000` in dev mode).

---

## Usage

### Web Interface

1. Start the server
2. Configure your validation job:
    - Source and target file paths (local or `gs://` GCS URIs)
    - Primary keys for row matching
    - File type and delimiter
    - Header rows, trailer patterns, encoding, compression
    - Normalization options (trim, case, date formatting, null handling)
3. Submit and monitor progress via live updates
4. Download HTML report or Excel workbook

### API Endpoints

| Method | Path                     | Description                        |
|--------|--------------------------|------------------------------------|
| `GET`  | `/`                      | Main UI page                       |
| `POST` | `/validate`              | Submit a validation job            |
| `POST` | `/upload`                | Upload files for validation        |
| `GET`  | `/status/{job_id}`       | Poll job progress                  |
| `GET`  | `/report/{job_id}`       | Download HTML report               |
| `GET`  | `/report/{job_id}/view`  | View HTML report inline in browser |
| `GET`  | `/report/{job_id}/excel` | Generate and download Excel report |
| `GET`  | `/cache/stats`           | On-disk result cache statistics    |

### Programmatic Usage

```python
import time
from file_validator.auditor import FileAuditor
from file_validator.config import FileConfig, NormalizationConfig
from file_validator.report_generator import generate_html_report
from file_validator.utils import calculate_time

source = FileConfig(
    path="data/source.csv",
    file_type="csv",
    delimiter=",",
    header_rows=1,
)

target = FileConfig(
    path="gs://bucket/target.csv.gz",  # GCS + compression
    file_type="csv",
    delimiter=",",
    header_rows=1,
)

norm = NormalizationConfig(
    trim_strings=True,
    treat_null_as_empty=True,
)

start = time.monotonic()

with FileAuditor(
        source_config=source,
        target_config=target,
        primary_keys=["id", "date"],
        norm_config=norm,
) as auditor:
    auditor.load_data()
    df = auditor.run_comparison()

    # For a 100% match, fetch sample rows
    sample_df = auditor.get_sample_data() if df.is_empty() else None

    generate_html_report(
        df=df,
        output_file="report.html",
        primary_keys=auditor.primary_keys,
        sample_df=sample_df,
        source_file=source.path,
        target_file=target.path,
        source_file_type=source.file_type,
        target_file_type=target.file_type,
        source_delimiter=source.delimiter,
        target_delimiter=target.delimiter,
        source_col_specs=source.col_specs,
        target_col_specs=target.col_specs,
        header_comparison=auditor.header_comparison,
        trailer_comparison=auditor.trailer_comparison,
        source_rejects=auditor.source_rejects,
        target_rejects=auditor.target_rejects,
        source_count=auditor.source_row_count,
        target_count=auditor.target_row_count,
        matching_rows=auditor.matching_rows_count,
        mismatched_rows=auditor.mismatched_rows_count,
        missing_in_source=auditor.missing_in_source_count,
        missing_in_target=auditor.missing_in_target_count,
        match_percentage=auditor.match_percentage,
        row_count_diff=auditor.row_count_diff,
    )

    print(f"Match: {auditor.match_percentage:.2f}%")

print(f"Elapsed: {calculate_time(start, time.monotonic())}")
```

---

## Key Features

### File Formats

| Format            | Details                                                                                        |
|-------------------|------------------------------------------------------------------------------------------------|
| Delimited         | CSV, PSV, TSV, any custom delimiter                                                            |
| Fixed-Width (FWF) | Column widths as comma-separated lengths (e.g. `10,5,8`); auto-converted to Parquet via Polars |
| Compression       | `.gz`, `.Z`, `.bz2`, `.zip` — auto-detected from extension                                     |
| Cloud Storage     | GCS `gs://` URIs — read directly via DuckDB httpfs or downloaded for FWF                       |

### Comparison Engine

- **Primary key matching** — multi-column composite keys, duplicate PK detection with auto-deduplication
- **Row-level comparison** — matches, mismatches, missing in source/target via efficient EXCEPT / anti-join
- **Column-level diff** — per-column match/mismatch status with source and target values
- **Character-by-character diff** — position-level comparison for mismatched header/trailer lines
- **Header/Trailer validation** — separate line-by-line comparison outside the data region
- **Data normalization** — trim (left/right/both), upper/lower case, accent stripping, date normalization, float
  epsilon, null-as-empty
- **Memory efficiency** — file-backed DuckDB database, spill-to-disk, configurable via env vars

### Interactive HTML Reports

- **Three view modes** — side-by-side, stacked, inline
- **Dark mode** — full theme with localStorage persistence
- **Search & filter** — global search across all columns
- **Navigation** — keyboard shortcuts, jump to differences
- **Character diff modal** — detailed char-by-char comparison with visual highlighting
- **Synchronized scrolling** — between source and target panes
- **Primary key highlighting** — 🔑 visual indicators for PK columns
- **File naming analysis** — component-by-component filename comparison
- **Copy to clipboard** — individual cell values
- **Timezone switching** — LOCAL, UTC, IST, ET
- **Event delegation** — efficient DOM handling for large result sets

### Excel Export

Multi-sheet workbooks (openpyxl) with styled headers:

| Sheet                    | Content                       |
|--------------------------|-------------------------------|
| Summary                  | Statistics and metadata       |
| Source-Target Comparison | Side-by-side data with status |
| Source Data              | Source values only            |
| Target Data              | Target values only            |
| Mismatch Details         | Filtered mismatched rows      |
| Header Comparison        | Header line differences       |
| Trailer Comparison       | Trailer line differences      |
| Sample Matching Data     | Sample rows for 100% match    |
| Rejected Records         | Rows rejected during parsing  |

---

## Configuration

### FileConfig

| Field              | Type                   | Default   | Description                                           |
|--------------------|------------------------|-----------|-------------------------------------------------------|
| `path`             | `str \| Path`          | —         | File path or `gs://` URI                              |
| `file_type`        | `str`                  | `"csv"`   | `csv`, `psv`, or `fwf`                                |
| `delimiter`        | `str`                  | `","`     | Delimiter for delimited files                         |
| `col_specs`        | `list[tuple[int,int]]` | `None`    | Column specs for FWF                                  |
| `header_rows`      | `int`                  | `0`       | Number of header rows to skip                         |
| `trailer_patterns` | `list[str]`            | `[]`      | Patterns to identify trailer rows                     |
| `column_names`     | `list[str]`            | `None`    | Override column names                                 |
| `compression`      | `str`                  | `"auto"`  | `auto`, `gzip`, `compress`, `bzip2`, `zip`, or `None` |
| `encoding`         | `str`                  | `"utf-8"` | File encoding                                         |

### NormalizationConfig

| Field                   | Type        | Default | Description                    |
|-------------------------|-------------|---------|--------------------------------|
| `float_epsilon`         | `float`     | `None`  | Tolerance for float comparison |
| `normalize_dates`       | `bool`      | `False` | Normalize date formats         |
| `trim_strings`          | `bool`      | `False` | Trim all string columns        |
| `treat_null_as_empty`   | `bool`      | `True`  | Treat NULL as empty string     |
| `ltrim_columns`         | `list[str]` | `[]`    | Columns to left-trim           |
| `rtrim_columns`         | `list[str]` | `[]`    | Columns to right-trim          |
| `trim_columns`          | `list[str]` | `[]`    | Columns to trim both sides     |
| `upper_columns`         | `list[str]` | `[]`    | Columns to uppercase           |
| `lower_columns`         | `list[str]` | `[]`    | Columns to lowercase           |
| `strip_accents_columns` | `list[str]` | `[]`    | Columns to strip accents       |

---

## DuckDB Tuning

Three DuckDB settings can be overridden via environment variables in `configs/.env`
(or shell exports) without changing any code. The env var always takes precedence
over the constructor parameter.

| Environment Variable               | Default | Description                                     |
|------------------------------------|---------|-------------------------------------------------|
| `DUCKDB_MEMORY_LIMIT`              | `6GB`   | Maximum RAM before spilling to disk             |
| `DUCKDB_PRESERVE_INSERTION_ORDER`  | `false` | Row-order tracking (`true`/`false`)             |
| `DUCKDB_ALLOCATOR_FLUSH_THRESHOLD` | `256MB` | How aggressively freed pages are returned to OS |

### Example (`configs/.env`)

```dotenv
DUCKDB_MEMORY_LIMIT="12GB"
DUCKDB_PRESERVE_INSERTION_ORDER="false"
DUCKDB_ALLOCATOR_FLUSH_THRESHOLD="512MB"
```

### Constructor Fallback

When the env var is **not** set, the constructor parameter is used:

```python
FileAuditor(
    source_config=source,
    target_config=target,
    primary_keys=["id"],
    memory_limit="16GB",  # used only when DUCKDB_MEMORY_LIMIT is absent
    threads=8,
)
```

---

## Development

### Quick Commands

```bash
# Sync workspace
uv sync

# Run all tests
bash scripts/run_tests.sh

# Run core package tests only
bash scripts/run_tests.sh core

# Run webserver package tests only
bash scripts/run_tests.sh webserver

# Run tests with verbose output
bash scripts/run_tests.sh all -v

# Start dev server (hot-reload)
bash scripts/start_server.sh dev

# Start production server
bash scripts/start_server.sh prod

```

### Project Tools

| Script                     | Purpose                                                  |
|----------------------------|----------------------------------------------------------|
| `scripts/start_server.sh`  | Start server — `dev` or `prod` mode (Bash)               |
| `scripts/start_server.ps1` | Start server — `dev` or `prod` mode (PowerShell)         |
| `scripts/start_server.bat` | Start server — `dev` or `prod` mode (CMD)                |
| `scripts/run_tests.sh`     | Run pytest suite — `all`/`core`/`webserver` (Bash)       |
| `scripts/run_tests.ps1`    | Run pytest suite — `all`/`core`/`webserver` (PowerShell) |

### Key Dependencies

| Package                | Purpose                              |
|------------------------|--------------------------------------|
| `duckdb`               | SQL-based comparison engine          |
| `polars`               | DataFrame operations, FWF conversion |
| `fastapi`              | Web server framework                 |
| `openpyxl`             | Excel workbook generation            |
| `jinja2`               | HTML report templating               |
| `pendulum`             | Timezone-aware timestamps            |
| `google-cloud-storage` | GCS file access                      |
| `pyarrow`              | Parquet I/O                          |
| `aiofiles`             | Async file I/O (web server)          |
| `ruff`                 | Linting and formatting               |

See [DEVELOPMENT.md](./DEVELOPMENT.md) for detailed development instructions.

---

## Documentation

- [file-validator-core/README.md](file-validator-core/README.md) — Core library
- [file-validator-webserver/README.md](file-validator-webserver/README.md) — Web UI
- [DEVELOPMENT.md](DEVELOPMENT.md) — Development guide

---

## Authentication

For GCS access, authentication is resolved in order:

1. **Service Account key** — via `GOOGLE_APPLICATION_CREDENTIALS` env var
2. **Workload Identity Pool** — external account with auto-refreshed OIDC tokens
3. **Application Default Credentials (ADC)** — `gcloud auth application-default login`
4. **DuckDB credential_chain** — fallback for httpfs extension

---

## Performance

- **File-backed DuckDB** — spills to disk instead of OOM; configurable via `DUCKDB_MEMORY_LIMIT` env var (default 6 GB)
- **EXCEPT set operations** — sort-merge friendly PK comparisons instead of expensive FULL OUTER JOIN
- **Materialized diff keys** — only differing PKs (capped at 500) are joined back for detail
- **Duplicate PK handling** — auto-detected and de-duplicated via materialized `ROW_NUMBER()` tables
- **Polars DataFrames** — zero-copy Parquet I/O, efficient FWF conversion
- **Async web layer** — non-blocking FastAPI with `ThreadPoolExecutor` for CPU-bound work
- **Configurable allocator** — `DUCKDB_ALLOCATOR_FLUSH_THRESHOLD` controls freed-page reclamation
- **Event delegation** — single DOM listener per event type in HTML reports
- **Deferred computation** — character diff computed on demand, not at page load

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Author

**Mayuresh Kedari**   <mayurkedari16@gmail.com>

---

## Support

1. Check [DEVELOPMENT.md](DEVELOPMENT.md) for troubleshooting
2. Review component READMEs for specific features
3. Contact the author
