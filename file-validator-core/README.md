# File Validator Core

**Version:** 1.0  
**Last Updated:** February 01, 2026

Core validation library for file comparison and auditing.

---

## 📚 Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Core Components](#core-components)
5. [File Format Support](#file-format-support)
6. [Configuration](#configuration)
7. [Comparison Engine](#comparison-engine)
8. [Report Features](#report-features)
9. [Excel Export](#excel-export)
10. [File Handlers](#file-handlers)
11. [Advanced Features](#advanced-features)
12. [DuckDB Tuning](#duckdb-tuning)
13. [API Reference](#api-reference)
14. [Troubleshooting](#troubleshooting)

---

## Overview

`file-validator-core` is a high-performance Python library for validating and comparing data files. Built on DuckDB and
Polars, it provides enterprise-grade file comparison with rich reporting capabilities.

### Key Features

- ✅ **DuckDB-powered SQL comparison engine** for efficient validation
- ✅ **Polars DataFrames** for high-performance data manipulation
- ✅ **Multi-format support**: CSV, PSV, TSV, Fixed-Width Files (FWF)
- ✅ **Compression handling**: .gz, .Z, .bz2, .zip automatic detection
- ✅ **Cloud storage**: Native Google Cloud Storage (GCS) integration
- ✅ **Interactive HTML reports** with dark mode and advanced UI
- ✅ **Excel export** with multi-sheet workbooks
- ✅ **Data normalization** with configurable transformation rules
- ✅ **Character-level diff** for detailed mismatch analysis

---

## Installation

### As Part of UV Workspace

```bash
# From repository root
uv sync
```

### Standalone Installation

```bash
# Install from local path
pip install -e ./file-validator-core

# Or with uv
uv pip install -e ./file-validator-core
```

### Dependencies

Core dependencies:

- `duckdb>=1.4.4` - High-performance SQL engine
- `polars>=1.38.1` - Fast DataFrames
- `pandas>=3.0.0` - Data manipulation (fallback)
- `pyarrow>=23.0.1` - Columnar format
- `openpyxl>=3.1.5` - Excel generation
- `google-cloud-storage>=3.9.0` - GCS integration
- `pendulum>=3.2.0` - DateTime handling
- `jinja2` - Template rendering
- `unlzw3>=0.2.3` - Unix compress decompression

---

## Quick Start

### Basic File Comparison

```python
import time
from file_validator.auditor import FileAuditor
from file_validator.config import FileConfig
from file_validator.report_generator import generate_html_report
from file_validator.utils import calculate_time

# Configure source and target files
source = FileConfig(
    path="data/source.csv",
    file_type="csv",
    delimiter=",",
    header_rows=1,
)

target = FileConfig(
    path="data/target.csv",
    file_type="csv",
    delimiter=",",
    header_rows=1,
)

start = time.monotonic()

# Use as a context manager — resources are cleaned up automatically
with FileAuditor(
    source_config=source,
    target_config=target,
    primary_keys=["id", "date"],
) as auditor:
    auditor.load_data()
    results = auditor.run_comparison()

    # For a 100% match, fetch a sample of matching rows
    sample_df = auditor.get_sample_data() if results.is_empty() else None

    generate_html_report(
        df=results,
        output_file="report.html",
        primary_keys=auditor.primary_keys,
        sample_df=sample_df,
        header_comparison=auditor.header_comparison,
        trailer_comparison=auditor.trailer_comparison,
        source_rejects=auditor.source_rejects,
        target_rejects=auditor.target_rejects,
        source_file=source.path,
        target_file=target.path,
        source_count=auditor.source_row_count,
        target_count=auditor.target_row_count,
        matching_rows=auditor.matching_rows_count,
        mismatched_rows=auditor.mismatched_rows_count,
        match_percentage=auditor.match_percentage,
        missing_in_source=auditor.missing_in_source_count,
        missing_in_target=auditor.missing_in_target_count,
        row_count_diff=auditor.row_count_diff,
    )

    print(f"Match percentage : {auditor.match_percentage:.2f}%")
    print(f"Matched rows     : {auditor.matching_rows_count:,}")
    print(f"Mismatched rows  : {auditor.mismatched_rows_count:,}")
    print(f"Missing in source: {auditor.missing_in_source_count:,}")
    print(f"Missing in target: {auditor.missing_in_target_count:,}")

print(f"Elapsed: {calculate_time(start, time.monotonic())}")
```

---

## Core Components

### 1. FileAuditor

The main comparison engine that orchestrates file loading and validation.

```python
from file_validator.auditor import FileAuditor
from file_validator.config import FileConfig, NormalizationConfig
import duckdb

auditor = FileAuditor(
    source_config=source,           # FileConfig
    target_config=target,           # FileConfig
    primary_keys=["id", "date"],    # list[str]
    norm_config=None,               # NormalizationConfig | None
    memory_limit="6GB",             # DuckDB RAM cap (overridable via env var)
    threads=4,                      # DuckDB thread count
    conn=None,                      # Optional pre-existing DuckDB connection
)
```

> **`conn` parameter:** when an external `duckdb.DuckDBPyConnection` is supplied the
> auditor reuses it and does **not** close it on exit. Intended for test fixtures
> that share a single in-memory database across multiple auditor instances.

**Workflow — call in order:**

```python
with FileAuditor(...) as auditor:
    auditor.load_data()                # 1. Load files into DuckDB views
    results = auditor.run_comparison() # 2. Run comparison, returns pl.DataFrame
    sample = auditor.get_sample_data() # 3. Optional — sample rows for 100% match
```

**Statistics attributes (populated after `run_comparison()`):**

```python
auditor.source_row_count  # int — rows in source
auditor.target_row_count  # int — rows in target
auditor.matching_rows_count  # int — rows that match exactly
auditor.mismatched_rows_count  # int — rows with value differences
auditor.missing_in_source_count  # int — keys in target but not source
auditor.missing_in_target_count  # int — keys in source but not target
auditor.match_percentage  # float — overall match %
auditor.row_count_diff  # int — abs(source_rows - target_rows)
```

**Comparison artifacts (populated after `load_data()`):**

```python
auditor.header_comparison  # list[dict] | None
auditor.trailer_comparison  # list[dict] | None
auditor.source_rejects  # pl.DataFrame | None — rows DuckDB rejected
auditor.target_rejects  # pl.DataFrame | None
```

### 2. FileConfig

Configuration dataclass for file parsing.

```python
from pathlib import Path
from file_validator.config import FileConfig

config = FileConfig(
    path="data/source.csv",          # str | Path — local path or gs:// URI
    file_type="csv",                  # 'csv', 'psv', or 'fwf'
    delimiter=",",                    # Field delimiter
    col_specs=None,                   # list[tuple[int,int]] | None — FWF column specs
    header_rows=0,                    # Header rows to skip
    trailer_patterns=[],              # list[str] — trailer row start patterns
    column_names=None,                # list[str] | None — override column names
    compression="auto",               # 'auto', 'gzip', 'compress', 'bzip2', 'zip', or None
    encoding="utf-8",                 # File encoding
)
```

**Properties:**

- `is_gcs` — `True` when path starts with `gs://`
- `is_compressed` — `True` when extension is `.gz`, `.Z`, `.bz2`, or `.zip`
- `filename` — bare filename extracted from path

### 3. NormalizationConfig

Data normalization rules applied before comparison.

```python
from file_validator.config import NormalizationConfig

norm_config = NormalizationConfig(
    float_epsilon=None,  # float | None — tolerance for float comparisons
    normalize_dates=False,  # bool — standardize date formats before comparing
    trim_strings=False,  # bool — trim whitespace from all string columns
    treat_null_as_empty=True,  # bool — treat NULL as "" (default: True)
    ltrim_columns=[],  # list[str] — left-trim specific columns
    rtrim_columns=[],  # list[str] — right-trim specific columns
    trim_columns=[],  # list[str] — both-sides trim specific columns
    upper_columns=[],  # list[str] — UPPER() specific columns
    lower_columns=[],  # list[str] — LOWER() specific columns
    strip_accents_columns=[],  # list[str] — UNACCENT() specific columns
)
```

> **Default `treat_null_as_empty=True`** — NULL values are treated as empty strings
> by default, preventing false mismatches between `NULL` and `""`.

---

## File Format Support

### Delimited Files (CSV, PSV, TSV)

```python
# CSV
csv_config = FileConfig(path="data.csv", file_type="csv", delimiter=",", header_rows=1)

# Pipe-separated (PSV)
psv_config = FileConfig(path="data.psv", file_type="psv", delimiter="|", header_rows=1)

# Tab-separated (TSV)
tsv_config = FileConfig(path="data.tsv", file_type="csv", delimiter="\t", header_rows=1)
```

### Fixed-Width Files (FWF)

`parse_fwf_column_specification` accepts a comma-separated list of **column widths**
(not ranges) and converts them to `(start, end)` tuples.

```python
from file_validator.utils import parse_fwf_column_specification

# "10,10,10" means three columns of 10 characters each
col_specs = parse_fwf_column_specification("10,10,10")
# Returns: [(0, 9), (10, 19), (20, 29)]

fwf_config = FileConfig(
    path="data.txt",
    file_type="fwf",
    col_specs=col_specs,
    column_names=["id", "name", "amount"],
    header_rows=1,
)
```

### Compressed Files

```python
# Gzip (.gz) — DuckDB handles natively
gz_config = FileConfig(path="data.csv.gz", compression="auto")

# Unix compress (.Z) — decompressed via unlzw3 or system uncompress
z_config = FileConfig(path="data.csv.Z", compression="compress")

# Bzip2 (.bz2)
bz2_config = FileConfig(path="data.csv.bz2", compression="bzip2")

# Zip (.zip)
zip_config = FileConfig(path="data.csv.zip", compression="zip")
```

### Google Cloud Storage

```python
gcs_config = FileConfig(
    path="gs://my-bucket/data/file.csv.gz",
    file_type="csv",
    delimiter=",",
    compression="auto",
)

# Authentication is configured via:
# - GOOGLE_APPLICATION_CREDENTIALS env var (service account JSON or WIP config)
# - Credential chain (ADC / gcloud CLI) as fallback
```

---

## Configuration

### Complete Configuration Example

```python
from file_validator.auditor import FileAuditor
from file_validator.config import FileConfig, NormalizationConfig

source = FileConfig(
    path="gs://bucket/source.csv.gz",
    file_type="csv",
    delimiter="|",
    header_rows=2,
    trailer_patterns=["TRAILER", "TOTAL", "END"],
    encoding="utf-8",
    compression="auto",
)

target = FileConfig(
    path="data/target.csv",
    file_type="csv",
    delimiter=",",
    header_rows=1,
    column_names=["id", "name", "amount", "date"],
)

norm_config = NormalizationConfig(
    float_epsilon=1e-6,
    normalize_dates=True,
    trim_strings=True,
    treat_null_as_empty=True,
    upper_columns=["name", "country_code"],
    trim_columns=["address", "description"],
)

with FileAuditor(
    source_config=source,
    target_config=target,
    primary_keys=["id", "date"],
    norm_config=norm_config,
    memory_limit="8GB",
    threads=8,
) as auditor:
    auditor.load_data()
    results = auditor.run_comparison()
```

---

## Comparison Engine

### DuckDB-Powered Architecture

The comparison engine uses DuckDB for efficient SQL-based validation:

1. **File Loading**: Parallel GCS downloads + native CSV/FWF readers
2. **Schema Alignment**: Automatic column name normalisation and type inference
3. **Primary Key Validation**: Duplicate PK detection with de-duplication
4. **Statistics**: EXCEPT set operations on PK columns (sort-merge, low memory)
5. **Detail Query**: Materialized `_diff_keys` table (capped at 500 rows) joined back to source/target
6. **Column Comparison**: Per-column CASE expressions with normalization applied
7. **Character Diff**: Character-by-character analysis for mismatched lines

### Comparison Process

```
┌─────────────────┐         ┌─────────────────┐
│  Source File    │         │  Target File    │
│  (local/GCS)    │         │  (local/GCS)    │
└────────┬────────┘         └────────┬────────┘
         │  Parallel GCS download    │
         ├───────────────────────────┤
         ▼                           ▼
    Decompress (.Z)           Decompress (.Z)
    Header/Trailer             Header/Trailer
    Extraction                 Extraction
         │                           │
         └─────────┬─────────────────┘
                   ▼
         Load into DuckDB (file-backed)
                   ▼
         Normalize column names
                   ▼
         Duplicate PK detection
                   ▼
         EXCEPT-based statistics
         (missing_in_source / target)
                   ▼
         Lightweight mismatch count
         (INNER JOIN on PKs only)
                   ▼
         Materialize _diff_keys (≤500)
                   ▼
         Detail JOIN with diff columns
                   ▼
            Results DataFrame
```

### Summary Statistics

After `run_comparison()` the following attributes are populated on the auditor:

```python
auditor.source_row_count  # 10000
auditor.target_row_count  # 10000
auditor.matching_rows_count  # 9500
auditor.mismatched_rows_count  # 400
auditor.missing_in_source_count  # 50
auditor.missing_in_target_count  # 50
auditor.match_percentage  # 95.0
auditor.row_count_diff  # 0
```

---

## Report Features

### Interactive HTML Reports

Generated reports include:

#### 1. **File Naming Convention Section**

- Side-by-side file cards (source / target)
- Full filename and path display
- Pattern analysis table and component comparison

#### 2. **Primary Key Visual Indicators**

- Dedicated Primary Keys section with stat boxes
- 🔑 emoji icons on PK column headers
- Enhanced legend with PK color explanation

#### 3. **View Modes**

- **Side-by-side**: Source and target in dual panes
- **Stacked**: Source over target in single pane
- **Inline**: Source/target columns alternating

#### 4. **Dark Mode Support**

- Full theme with WCAG AAA compliant contrast ratios
- Persistent preference (localStorage)

#### 5. **Interactive Features**

- **Search & Filter**: Global search, filter by status
- **Navigation**: Keyboard shortcuts, jump to differences
- **Character Diff**: Modal with char-by-char comparison
- **Synchronized Scrolling**: Between source/target panes
- **Copy Buttons**: Copy cell values to clipboard
- **Timezone Switching**: LOCAL, UTC, IST, ET

#### 6. **Data Quality Insights**

- Match percentage gauge
- Row distribution charts
- Column-level statistics

### Report Generation

```python
from file_validator.report_generator import generate_html_report

generate_html_report(
    df=results,
    output_file="report.html",
    primary_keys=auditor.primary_keys,
    sample_df=sample_df,
    header_comparison=auditor.header_comparison,
    trailer_comparison=auditor.trailer_comparison,
    source_rejects=auditor.source_rejects,
    target_rejects=auditor.target_rejects,
    source_file=source.path,
    target_file=target.path,
    source_file_type=source.file_type,
    target_file_type=target.file_type,
    source_delimiter=source.delimiter,
    target_delimiter=target.delimiter,
    source_col_specs=source.col_specs,
    target_col_specs=target.col_specs,
    # Summary stats passed as kwargs
    source_count=auditor.source_row_count,
    target_count=auditor.target_row_count,
    matching_rows=auditor.matching_rows_count,
    mismatched_rows=auditor.mismatched_rows_count,
    match_percentage=auditor.match_percentage,
    missing_in_source=auditor.missing_in_source_count,
    missing_in_target=auditor.missing_in_target_count,
    row_count_diff=auditor.row_count_diff,
)
```

---

## Excel Export

### Multi-Sheet Workbooks

Exported Excel files contain:

| Sheet                        | Content                                    |
|------------------------------|--------------------------------------------|
| **Summary**                  | Statistics and metadata                    |
| **Source-Target Comparison** | Side-by-side data with status              |
| **Source Data**              | Source values only                         |
| **Target Data**              | Target values only                         |
| **Mismatch Details**         | Filtered mismatched rows                   |
| **Header Comparison**        | Header line differences                    |
| **Trailer Comparison**       | Trailer line differences                   |
| **Sample Matching Data**     | Sample rows for 100% match scenarios       |
| **Rejected Records**         | Validation failures from source and target |

### Usage

```python
from file_validator.excel_exporter import build_and_save_excel_file
from pathlib import Path

build_and_save_excel_file(
    df=results,
    primary_keys=auditor.primary_keys,
    output_file=Path("output/comparison.xlsx"),
    sample_df=sample_df,
    header_comparison=auditor.header_comparison,
    trailer_comparison=auditor.trailer_comparison,
    source_rejects=auditor.source_rejects,
    target_rejects=auditor.target_rejects,
)
```

---

## File Handlers

### Handler Architecture

```python
from abc import ABC, abstractmethod

class FileHandler(ABC):
    def get_file(self, path: str | Path, decompress: bool = True) -> Path
    def get_file_info(self, path: str | Path) -> dict
    def prepare_for_duckdb(self, path: str | Path, temp_dir: Path | None = None) -> tuple[Path, list[Path]]
    def cleanup(self) -> None
    def close(self) -> None
    def __enter__(self) -> Self
    def __exit__(self, exc_type, exc_val, exc_tb) -> None
```

### LocalFileHandler

```python
from file_validator.file_handlers import LocalFileHandler

with LocalFileHandler() as handler:
    file_path = handler.get_file("data/file.csv.gz", decompress=True)
    info = handler.get_file_info("data/file.csv.gz")
    # info keys: original_path, is_local, compression, filename, size_bytes, exists
```

### GCSFileHandler

```python
from file_validator.file_handlers import GCSFileHandler

with GCSFileHandler() as handler:
    file_path = handler.get_file("gs://bucket/file.csv.gz", decompress=True)
    info = handler.get_file_info("gs://bucket/file.csv.gz")
    # info keys: original_path, is_gcs, compression, filename, bucket, blob_path, size_bytes, exists
```

### Compression Utilities

```python
from file_validator.file_handlers.compression import (
    get_compression_type,
    decompress_file,
    COMPRESSION_EXTENSIONS,
)

get_compression_type("file.csv.gz")   # 'gzip'
get_compression_type("file.csv.Z")    # 'compress'
get_compression_type("file.csv.bz2")  # 'bzip2'
get_compression_type("file.csv")      # None

decompressed = decompress_file(
    input_path=Path("file.csv.gz"),
    output_path=Path("file.csv"),
    compression_type="gzip",        # optional — auto-detected if None
)

# Supported extensions
print(COMPRESSION_EXTENSIONS)
# {'.gz': 'gzip', '.gzip': 'gzip', '.z': 'compress', '.Z': 'compress',
#  '.bz2': 'bzip2', '.zip': 'zip'}
```

---

## Advanced Features

### Data Normalization

```python
norm_config = NormalizationConfig(
    float_epsilon=0.001,  # Treat values within 0.001 as equal
    trim_strings=True,  # Trim whitespace from all string columns
    treat_null_as_empty=True,  # NULL == "" (default)
    normalize_dates=True,  # Standardize date formats via TIMESTAMP cast
    upper_columns=["country_code", "status"],
    lower_columns=["email"],
    trim_columns=["address", "description"],
    ltrim_columns=["code"],
    rtrim_columns=["suffix"],
    strip_accents_columns=["name"],
)
```

### Character-Level Diff

`_char_diff` is a module-level helper used internally by `_compare_lines`:

```python
from file_validator.auditor import _char_diff

diffs = _char_diff("Hello World", "Hello World!")
# [{"pos": 11, "src": None, "tgt": "!", "match": False}]

diffs = _char_diff("ABC123", "ABC124")
# [{"pos": 5, "src": "3", "tgt": "4", "match": False}]
```

### Header / Trailer Handling

```python
config = FileConfig(
    path="data.csv",
    header_rows=2,                              # First 2 lines are headers
    trailer_patterns=["TRAILER", "TOTAL", "EOF"],  # Lines starting with these are trailers
)

with FileAuditor(source, target, primary_keys) as auditor:
    auditor.load_data()
    # Headers and trailers are extracted and compared automatically
    print(auditor.header_comparison)   # list[dict] with MATCH/MISMATCH per line
    print(auditor.trailer_comparison)  # list[dict] with MATCH/MISMATCH per line
```

### OAuth2 / OIDC for GCS

```python
from file_validator.credentials import (
    auto_refresh_oidc_token_if_needed,
    get_credentials_and_project,
    impersonate_self,
)

# Refresh OIDC token if nearing expiry (uses OIDC_* env vars)
auto_refresh_oidc_token_if_needed()

# Load credentials from GOOGLE_APPLICATION_CREDENTIALS
credentials, project_id = get_credentials_and_project()

# Impersonate a service account (uses TARGET_PRINCIPAL env var)
impersonated = impersonate_self(credentials, target_principal="sa@project.iam.gserviceaccount.com")
```

---

## DuckDB Tuning

Three DuckDB settings can be overridden via environment variables without changing
code. The env var always takes precedence over the constructor parameter.

| Environment Variable               | Default                   | Description                                     |
|------------------------------------|---------------------------|-------------------------------------------------|
| `DUCKDB_MEMORY_LIMIT`              | `6GB` (constructor param) | Maximum RAM before spilling to disk             |
| `DUCKDB_PRESERVE_INSERTION_ORDER`  | `false`                   | Re-enable row-order tracking (`true`/`false`)   |
| `DUCKDB_ALLOCATOR_FLUSH_THRESHOLD` | `256MB`                   | How aggressively freed pages are returned to OS |

### Setting via `.env` (configs/.env)

```dotenv
# Increase RAM cap for large files
DUCKDB_MEMORY_LIMIT="12GB"

# Re-enable insertion-order tracking (higher memory, deterministic output)
DUCKDB_PRESERVE_INSERTION_ORDER="true"

# Tune C allocator page-return aggressiveness
DUCKDB_ALLOCATOR_FLUSH_THRESHOLD="512MB"
```

### Setting via constructor (still respected when env var is absent)

```python
FileAuditor(
    source_config=source,
    target_config=target,
    primary_keys=["id"],
    memory_limit="16GB",  # used only if DUCKDB_MEMORY_LIMIT is not set
    threads=8,
)
```

---

## API Reference

### Main Classes

| Class                 | Module                        | Purpose                         |
|-----------------------|-------------------------------|---------------------------------|
| `FileAuditor`         | `auditor`                     | Main comparison engine          |
| `FileConfig`          | `config`                      | File configuration              |
| `NormalizationConfig` | `config`                      | Normalization rules             |
| `FileHandler`         | `file_handlers.interface`     | Abstract base for file handlers |
| `GCSFileHandler`      | `file_handlers.gcs_handler`   | GCS file operations             |
| `LocalFileHandler`    | `file_handlers.local_handler` | Local file operations           |
| `PolarsFWFConverter`  | `converters`                  | FWF → Parquet conversion        |

### Main Functions

| Function                         | Module                      | Purpose                                           |
|----------------------------------|-----------------------------|---------------------------------------------------|
| `generate_html_report`           | `report_generator`          | Create interactive HTML report                    |
| `build_and_save_excel_file`      | `excel_exporter`            | Export results to Excel                           |
| `export_to_excel`                | `excel_exporter`            | Lower-level Excel export                          |
| `decompress_file`                | `file_handlers.compression` | Decompress a file                                 |
| `get_compression_type`           | `file_handlers.compression` | Detect compression from extension                 |
| `parse_fwf_column_specification` | `utils`                     | Parse column widths → `(start, end)` tuples       |
| `setup_logging`                  | `utils`                     | Configure rotating file + console logging         |
| `format_bytes`                   | `utils`                     | Convert byte count to human-readable string       |
| `calculate_time`                 | `utils`                     | Format elapsed seconds as human-readable duration |

### Utility Functions

```python
from file_validator.utils import (
    calculate_time,
    format_bytes,
    parse_fwf_column_specification,
    setup_logging,
)
import time

# Measure elapsed time
start = time.monotonic()
# ... work ...
elapsed = calculate_time(start, time.monotonic())
# "3 min 42 sec"

# Format file sizes
format_bytes(1024000)          # "1.02 MB"
format_bytes(1536, binary=True) # "1.50 KiB"

# Parse FWF column widths → (start, end) tuples
parse_fwf_column_specification("10,5,8")
# [(0, 9), (10, 14), (15, 22)]

# Configure logging (writes timestamped file to logs/core/ by default)
setup_logging(log_level="INFO", log_file="logs/validation.log")
```

---

## Troubleshooting

### Common Issues

#### Import Errors

```bash
# Ensure workspace is synced
uv sync --force

# Or install package directly
uv pip install -e ./file-validator-core
```

#### GCS Authentication

```bash
# Set service account credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"

# Or use gcloud CLI
gcloud auth application-default login

# Verify
python -c "from google.auth import default; creds, project = default(); print(project)"
```

#### Memory Errors

Use the env var to increase the limit without changing code:

```bash
# In configs/.env or shell
export DUCKDB_MEMORY_LIMIT="16GB"
```

Or pass the parameter directly:

```python
FileAuditor(source, target, primary_keys=["id"], memory_limit="16GB", threads=8)
```

#### Compression Errors

For `.Z` files, ensure the `unlzw3` package is installed (it is a declared dependency)
or that the system `uncompress` utility is on `PATH`:

```bash
which uncompress      # Linux/Mac
pip install unlzw3    # fallback pure-Python implementation
```

#### Large File Performance

```bash
# Tune DuckDB via env vars
export DUCKDB_MEMORY_LIMIT="32GB"
export DUCKDB_ALLOCATOR_FLUSH_THRESHOLD="512MB"
```

```python
FileAuditor(source, target, primary_keys=["id"], memory_limit="32GB", threads=16)
```

### Debug Logging

```python
from file_validator.utils import setup_logging

setup_logging(log_level="DEBUG", log_file="logs/debug.log")
```

---

## Performance Tips

1. **Use compression**: Compressed files reduce GCS transfer time
2. **Tune memory**: Set `DUCKDB_MEMORY_LIMIT` for your data size
3. **Parallelize**: Increase `threads` for larger files
4. **Normalize wisely**: Apply only the normalization rules you need
5. **Primary keys**: Choose the smallest set of columns that uniquely identify a row

### Benchmarks

Typical performance on modern hardware:

| File Size | Rows | Comparison Time |
|-----------|------|-----------------|
| 10 MB     | 100K | ~2 seconds      |
| 100 MB    | 1M   | ~15 seconds     |
| 1 GB      | 10M  | ~2 minutes      |
| 10 GB     | 100M | ~20 minutes     |

*Times vary based on column count, normalization complexity, and hardware.*

---

## Development

### Running Tests

```bash
# From repository root
uv run pytest file-validator-core/tests/

# With coverage
uv run pytest --cov=file_validator file-validator-core/tests/

# Verbose output
uv run pytest -v file-validator-core/tests/
```

### Building from Source

```bash
cd file-validator-core
uv build

# Output in dist/
ls dist/
# file_validator_core-0.1.0-py3-none-any.whl
# file_validator_core-0.1.0.tar.gz
```

### Code Quality

```bash
# Run ruff linter
uv run ruff check src/

# Run ruff formatter
uv run ruff format src/

# Run mypy type checker
uv run mypy src/
```

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Author

**Mayuresh Kedari**   <mayurkedari16@gmail.com>

---

## See Also

- [File Validator WebServer](../file-validator-webserver/README.md) - Web UI
- [Main README](../README.md) - Project overview

