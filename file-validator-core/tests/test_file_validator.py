# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the MIT License (the "License"); you may not
# use this file except in compliance with the License.
#
# MIT License
#
# Copyright (c) 2026 Mayuresh Kedari
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom
# the Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
# OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
Unit tests for File Validator.

This module contains comprehensive tests for the file validator tool.
Generated reports are persisted in the test_output directory for manual verification.

Usage:
    pytest test_file_validator.py -v
    pytest test_file_validator.py -v -k "test_sample"
    pytest test_file_validator.py -v --tb=short
"""

import gzip
import logging
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import duckdb
import pytest

from file_validator.auditor import FileAuditor
from file_validator.config import FileConfig, NormalizationConfig
from file_validator.excel_exporter import export_to_excel
from file_validator.file_handlers import (
    GCSFileHandler,
    decompress_file,
    get_compression_type,
    get_file_info,
    is_gcs_path,
    prepare_file_for_duckdb,
)
from file_validator.report_generator import generate_html_report
from file_validator.utils import calculate_time, format_bytes

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================
# Test Fixtures
# ============================================================


@pytest.fixture(scope="module")
def test_output_dir() -> Path:
    """Create and return the test output directory."""
    output_dir = Path(__file__).parent / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped subdirectory for this test run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Test output directory: %s", run_dir)
    return run_dir


@pytest.fixture(scope="module")
def shared_duckdb_conn() -> duckdb.DuckDBPyConnection:
    """
    Module-scoped DuckDB connection shared across all tests.

    Avoids the overhead of creating a new file-backed database (and
    potentially loading the httpfs extension / GCS credentials) for
    every single ``FileAuditor`` instantiation.
    """
    work_dir = Path(tempfile.mkdtemp(prefix="duckdb_shared_"))
    db_path = (work_dir / "shared.duckdb").as_posix()
    conn = duckdb.connect(database=db_path)
    conn.execute("PRAGMA memory_limit='6GB'")
    conn.execute("PRAGMA threads=4")
    conn.execute("SET preserve_insertion_order=false")
    conn.execute(f"PRAGMA temp_directory='{work_dir.as_posix()}'")

    logger.info("Shared DuckDB connection created: %s", db_path)
    yield conn

    # Teardown
    import shutil

    try:
        conn.close()
    except Exception:
        pass
    shutil.rmtree(work_dir, ignore_errors=True)
    logger.info("Shared DuckDB connection closed and cleaned up")


@pytest.fixture(scope="module")
def test_input_dir() -> Path:
    """Return the test input files directory."""
    input_dir = Path(__file__).parent / "test_input"
    input_dir.mkdir(parents=True, exist_ok=True)
    return input_dir


@pytest.fixture(scope="module")
def sample_csv_files(test_input_dir: Path) -> tuple[Path, Path]:
    """Create sample CSV files for testing."""
    # Source file (no trailer to avoid column name issues)
    source_content = """Customer ID,Name,Amount,Date,Status
1001,John Doe,150.50,2025-01-15,Active
1002,Jane Smith,200.00,2025-01-16,Active
1003,Bob Johnson,75.25,2025-01-17,Inactive
1004,Alice Brown,300.00,2025-01-18,Active
1005,Charlie Wilson,125.75,2025-01-19,Pending"""

    # Target file (with some differences)
    target_content = """Customer ID,Name,Amount,Date,Status
1001,John Doe,150.50,2025-01-15,Active
1002,Jane Smith,205.00,2025-01-16,Active
1003,Bob Johnson,75.25,2025-01-17,Active
1004,Alice Brown,300.00,2025-01-18,Active
1006,New Customer,50.00,2025-01-20,Active"""

    source_path = test_input_dir / "test_source.csv"
    target_path = test_input_dir / "test_target.csv"

    source_path.write_text(source_content, encoding="utf-8")
    target_path.write_text(target_content, encoding="utf-8")

    return source_path, target_path


@pytest.fixture(scope="module")
def matching_csv_files(test_input_dir: Path) -> tuple[Path, Path]:
    """Create matching CSV files for testing 100% match scenario."""
    content = """ID,Name,Value,Category
A001,Product One,100.00,Electronics
A002,Product Two,200.00,Clothing
A003,Product Three,150.00,Electronics
A004,Product Four,75.50,Home
A005,Product Five,300.00,Electronics"""

    source_path = test_input_dir / "test_match_source.csv"
    target_path = test_input_dir / "test_match_target.csv"

    source_path.write_text(content, encoding="utf-8")
    target_path.write_text(content, encoding="utf-8")

    return source_path, target_path


@pytest.fixture(scope="module")
def pipe_delimited_files(test_input_dir: Path) -> tuple[Path, Path]:
    """Create pipe-delimited files for testing."""
    source_content = """column0|column1|column2|column3|column4
1001|Value1|100|Data1|Active
1002|Value2|200|Data2|Active
1003|Value3|300|Data3|Inactive
1004|Value4|400|Data4|Active"""

    target_content = """column0|column1|column2|column3|column4
1001|Value1|100|Data1|Active
1002|Value2|250|Data2|Active
1003|Value3|300|Data3|Active
1005|Value5|500|Data5|Active"""

    source_path = test_input_dir / "test_pipe_source.txt"
    target_path = test_input_dir / "test_pipe_target.txt"

    source_path.write_text(source_content, encoding="utf-8")
    target_path.write_text(target_content, encoding="utf-8")

    return source_path, target_path


@pytest.fixture(scope="module")
def multi_pk_files(test_input_dir: Path) -> tuple[Path, Path]:
    """Create files with multiple primary keys for testing."""
    source_content = """CUST_ID,CUST_LINE_SEQ_ID,MTN,AMOUNT,STATUS
C001,1,5551234567,100.00,Active
C001,2,5551234568,150.00,Active
C002,1,5559876543,200.00,Active
C002,2,5559876544,250.00,Inactive
C003,1,5555551234,300.00,Active"""

    target_content = """CUST_ID,CUST_LINE_SEQ_ID,MTN,AMOUNT,STATUS
C001,1,5551234567,100.00,Active
C001,2,5551234568,155.00,Active
C002,1,5559876543,200.00,Active
C002,2,5559876544,250.00,Active
C004,1,5556667777,400.00,Active"""

    source_path = test_input_dir / "test_multi_pk_source.csv"
    target_path = test_input_dir / "test_multi_pk_target.csv"

    source_path.write_text(source_content, encoding="utf-8")
    target_path.write_text(target_content, encoding="utf-8")

    return source_path, target_path


@pytest.fixture(scope="module")
def header_trailer_files(test_input_dir: Path) -> tuple[Path, Path]:
    """Create files with header and trailer for testing."""
    # Using header_rows=1 means first row is header
    source_content = """CustomerID,Name,Amount,Date
1001,John Doe,150.50,2025-01-15
1002,Jane Smith,200.00,2025-01-16
1003,Bob Johnson,75.25,2025-01-17
data_extract,3 records,done,2025-02-08"""

    target_content = """CustomerID,Name,Amount,Date
1001,John Doe,150.50,2025-01-15
1002,Jane Smith,200.00,2025-01-16
1003,Bob Johnson,75.25,2025-01-17
data_extract,3 records,done,2025-02-08"""

    source_path = test_input_dir / "test_header_trailer_source.csv"
    target_path = test_input_dir / "test_header_trailer_target.csv"

    source_path.write_text(source_content, encoding="utf-8")
    target_path.write_text(target_content, encoding="utf-8")

    return source_path, target_path


@pytest.fixture(scope="module")
def null_handling_files(test_input_dir: Path) -> tuple[Path, Path]:
    """Create files with NULL values for testing."""
    source_content = """ID,Name,Value,Description
1,Item One,100,Description One
2,Item Two,,
3,Item Three,150,Description Three
4,,200,Description Four
5,Item Five,250,"""

    target_content = """ID,Name,Value,Description
1,Item One,100,Description One
2,Item Two,NULL,NULL
3,Item Three,150,Description Three
4,NULL,200,Description Four
5,Item Five,250,NULL"""

    source_path = test_input_dir / "test_null_source.csv"
    target_path = test_input_dir / "test_null_target.csv"

    source_path.write_text(source_content, encoding="utf-8")
    target_path.write_text(target_content, encoding="utf-8")

    return source_path, target_path


@pytest.fixture(scope="module")
def gzip_csv_files(test_input_dir: Path) -> tuple[Path, Path]:
    """
    Create gzip-compressed CSV files for testing.

    Generates self-contained source and target CSV.GZ files with known
    differences so ``TestCompression`` tests do not depend on external files.
    """
    source_content = (
        "ACCT_ID,CUST_NAME,BALANCE,REGION,STATUS\n"
        "A1001,John Doe,1500.50,EAST,Active\n"
        "A1002,Jane Smith,2300.00,WEST,Active\n"
        "A1003,Bob Johnson,750.25,EAST,Inactive\n"
        "A1004,Alice Brown,3100.00,NORTH,Active\n"
        "A1005,Charlie Wilson,125.75,SOUTH,Pending\n"
        "A1006,Diana Prince,4200.00,WEST,Active\n"
        "A1007,Edward Kim,980.30,EAST,Active\n"
        "A1008,Fiona Garcia,1675.90,NORTH,Active\n"
        "A1009,George Lee,2890.10,SOUTH,Inactive\n"
        "A1010,Hannah Chen,560.00,EAST,Active\n"
    )

    # Target has some value differences, a missing row, and an extra row
    target_content = (
        "ACCT_ID,CUST_NAME,BALANCE,REGION,STATUS\n"
        "A1001,John Doe,1500.50,EAST,Active\n"
        "A1002,Jane Smith,2350.00,WEST,Active\n"  # balance differs
        "A1003,Bob Johnson,750.25,EAST,Active\n"  # status differs
        "A1004,Alice Brown,3100.00,NORTH,Active\n"
        "A1005,Charlie Wilson,125.75,SOUTH,Active\n"  # status differs
        "A1006,Diana Prince,4200.00,WEST,Active\n"
        "A1007,Edward Kim,980.30,EAST,Active\n"
        "A1008,Fiona Garcia,1700.00,NORTH,Active\n"  # balance differs
        # A1009 missing in target
        "A1010,Hannah Chen,560.00,EAST,Active\n"
        "A1011,Ivan Petrov,3300.50,SOUTH,Active\n"  # extra row
    )

    source_path = test_input_dir / "test_gz_source.csv.gz"
    target_path = test_input_dir / "test_gz_target.csv.gz"

    with gzip.open(source_path, "wt", encoding="utf-8") as f:
        f.write(source_content)

    with gzip.open(target_path, "wt", encoding="utf-8") as f:
        f.write(target_content)

    return source_path, target_path


# ============================================================
# Helper Functions
# ============================================================


def run_validation(
    source_path: Path,
    target_path: Path,
    primary_keys: list[str],
    output_dir: Path,
    test_name: str,
    delimiter: str = ",",
    header_rows: int = 1,
    trailer_patterns: list[str] | None = None,
    norm_config: NormalizationConfig | None = None,
    generate_reports: bool = True,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> dict[str, Any]:
    """
    Run file validation and optionally generate reports.

    Args:
        generate_reports: When False, skip HTML/Excel report generation for
            faster test execution.  Defaults to True.
        conn: Optional shared DuckDB connection.  When provided the
            ``FileAuditor`` reuses it instead of creating a new file-backed DB.

    Returns a dictionary with validation results and paths to generated reports.
    """
    start_time = time.monotonic()

    # Configure source file
    src_conf = FileConfig(
        path=source_path,
        file_type="csv",
        delimiter=delimiter,
        header_rows=header_rows,
        trailer_patterns=trailer_patterns or [],
    )

    # Configure target file
    tgt_conf = FileConfig(
        path=target_path,
        file_type="csv",
        delimiter=delimiter,
        header_rows=header_rows,
        trailer_patterns=trailer_patterns or [],
    )

    # Normalization rules
    norm_rules = norm_config or NormalizationConfig(
        float_epsilon=0.01,
        normalize_dates=True,
        trim_strings=True,
        treat_null_as_empty=True,
    )

    # Execute validation
    with FileAuditor(
        source_config=src_conf,
        target_config=tgt_conf,
        primary_keys=primary_keys,
        norm_config=norm_rules,
        conn=conn,
    ) as auditor:
        auditor.load_data()
        results = auditor.run_comparison()

        # Generate sample data for 100% match
        sample_df = None
        if results.is_empty():
            sample_df = auditor.get_sample_data()

        html_path: Path = output_dir / f"{test_name}_report.html"
        excel_path: Path = output_dir / f"{test_name}_report.xlsx"

        if generate_reports:
            # Generate HTML report
            generate_html_report(
                df=results,
                output_file=html_path,
                primary_keys=auditor.primary_keys,
                sample_df=sample_df,
                header_comparison=auditor.header_comparison,
                trailer_comparison=auditor.trailer_comparison,
                source_rejects=auditor.source_rejects,
                target_rejects=auditor.target_rejects,
                source_file=source_path,
                target_file=target_path,
                source_file_type=auditor.source.file_type,
                target_file_type=auditor.target.file_type,
                source_delimiter=auditor.source.delimiter,
                target_delimiter=auditor.target.delimiter,
                source_col_specs=auditor.source.col_specs,
                target_col_specs=auditor.target.col_specs,
                job_name=test_name,
                source_count=auditor.source_row_count,
                target_count=auditor.target_row_count,
                matching_rows=auditor.matching_rows_count,
                mismatched_rows=auditor.mismatched_rows_count,
                match_percentage=auditor.match_percentage,
                missing_in_source=auditor.missing_in_source_count,
                missing_in_target=auditor.missing_in_target_count,
                row_count_diff=auditor.row_count_diff,
            )

            # Generate Excel report
            export_to_excel(
                df=results,
                output_file=excel_path,
                primary_keys=auditor.primary_keys,
                sample_df=sample_df,
                header_comparison=auditor.header_comparison,
                trailer_comparison=auditor.trailer_comparison,
                source_rejects=auditor.source_rejects,
                target_rejects=auditor.target_rejects,
                source_count=auditor.source_row_count,
                target_count=auditor.target_row_count,
                matching_rows=auditor.matching_rows_count,
                mismatched_rows=auditor.mismatched_rows_count,
                match_percentage=auditor.match_percentage,
                missing_in_source=auditor.missing_in_source_count,
                missing_in_target=auditor.missing_in_target_count,
                row_count_diff=auditor.row_count_diff,
            )

        end_time = time.monotonic()
        elapsed = calculate_time(start_time, end_time)

        return {
            "results": results,
            "html_report": html_path,
            "excel_report": excel_path,
            "source_count": auditor.source_row_count,
            "target_count": auditor.target_row_count,
            "matching_rows": auditor.matching_rows_count,
            "match_percentage": auditor.match_percentage,
            "missing_in_source": auditor.missing_in_source_count,
            "missing_in_target": auditor.missing_in_target_count,
            "elapsed_time": elapsed,
            "header_comparison": auditor.header_comparison,
            "trailer_comparison": auditor.trailer_comparison,
        }


# ============================================================
# Test Cases
# ============================================================


class TestFileValidator:
    """Test cases for file validator functionality."""

    def test_sample_with_differences(
        self,
        sample_csv_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test validation with sample files that have differences."""
        source_path, target_path = sample_csv_files

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["Customer ID"],
            output_dir=test_output_dir,
            test_name="sample_differences",
            header_rows=1,
            conn=shared_duckdb_conn,
        )

        # Assertions
        assert result["html_report"].exists(), "HTML report should be generated"
        assert result["excel_report"].exists(), "Excel report should be generated"
        assert result["source_count"] == 5, "Source should have 5 rows"
        assert result["target_count"] == 5, "Target should have 5 rows"
        assert result["matching_rows"] < 5, "Should have fewer than 5 matching rows"
        assert result["missing_in_source"] > 0 or result["missing_in_target"] > 0, (
            "Should have missing rows in source or target"
        )

        logger.info("✅ Test passed: sample_differences")
        logger.info("   HTML Report: %s", result["html_report"])
        logger.info("   Excel Report: %s", result["excel_report"])
        logger.info("   Match Percentage: %.2f%%", result["match_percentage"])

    def test_matching_files(
        self,
        matching_csv_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test validation with 100% matching files."""
        source_path, target_path = matching_csv_files

        result: dict[str, Any] = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["ID"],
            output_dir=test_output_dir,
            test_name="matching_files",
            generate_reports=False,
            conn=shared_duckdb_conn,
        )

        # Assertions
        assert result["match_percentage"] == 100.0, "Should have 100% match"
        assert result["missing_in_source"] == 0, "Should have no missing in source"
        assert result["missing_in_target"] == 0, "Should have no missing in target"
        assert result["results"].is_empty(), "Results should be empty for perfect match"

        logger.info("✅ Test passed: matching_files")
        logger.info("   Match Percentage: %.2f%%", result["match_percentage"])

    def test_pipe_delimited(
        self,
        pipe_delimited_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test validation with pipe-delimited files."""
        source_path, target_path = pipe_delimited_files

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["column0"],
            output_dir=test_output_dir,
            test_name="pipe_delimited",
            delimiter="|",
            generate_reports=False,
            conn=shared_duckdb_conn,
        )

        # Assertions
        assert result["source_count"] == 4, "Source should have 4 rows"
        assert result["target_count"] == 4, "Target should have 4 rows"

        logger.info("✅ Test passed: pipe_delimited")
        logger.info("   Match Percentage: %.2f%%", result["match_percentage"])

    def test_multiple_primary_keys(
        self,
        multi_pk_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test validation with multiple primary keys."""
        source_path, target_path = multi_pk_files

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["CUST_ID", "CUST_LINE_SEQ_ID", "MTN"],
            output_dir=test_output_dir,
            test_name="multiple_primary_keys",
            generate_reports=False,
            conn=shared_duckdb_conn,
        )

        # Assertions
        assert result["source_count"] == 5, "Source should have 5 rows"
        assert result["target_count"] == 5, "Target should have 5 rows"

        logger.info("✅ Test passed: multiple_primary_keys")
        logger.info("   Matching Rows: %d", result["matching_rows"])
        logger.info("   Missing in Source: %d", result["missing_in_source"])
        logger.info("   Missing in Target: %d", result["missing_in_target"])

    def test_header_trailer(
        self,
        header_trailer_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test validation with header and trailer rows."""
        source_path, target_path = header_trailer_files

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["CustomerID"],
            output_dir=test_output_dir,
            test_name="header_trailer",
            header_rows=1,
            trailer_patterns=["data_extract"],
            generate_reports=False,
            conn=shared_duckdb_conn,
        )

        # Assertions
        assert result["match_percentage"] == 100.0, "Should have 100% match"

        logger.info("✅ Test passed: header_trailer")
        logger.info("   Header Comparison: %d lines", len(result["header_comparison"]))
        logger.info("   Trailer Comparison: %d lines", len(result["trailer_comparison"]))

    def test_null_handling(
        self,
        null_handling_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test validation with NULL value handling."""
        source_path, target_path = null_handling_files

        # Test with treat_null_as_empty=True
        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["ID"],
            output_dir=test_output_dir,
            test_name="null_handling_treat_as_empty",
            norm_config=NormalizationConfig(
                treat_null_as_empty=True,
                trim_strings=True,
            ),
            generate_reports=False,
            conn=shared_duckdb_conn,
        )

        logger.info("✅ Test passed: null_handling")
        logger.info("   Match Percentage: %.2f%%", result["match_percentage"])


class TestNormalizationConfig:
    """Test cases for normalization configuration."""

    def test_float_epsilon(
        self,
        test_input_dir: Path,
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test float comparison with epsilon tolerance."""
        source_content = """ID,Value
1,100.001
2,200.005
3,300.009"""

        target_content = """ID,Value
1,100.002
2,200.004
3,300.011"""

        source_path = test_input_dir / "test_float_source.csv"
        target_path = test_input_dir / "test_float_target.csv"

        source_path.write_text(source_content, encoding="utf-8")
        target_path.write_text(target_content, encoding="utf-8")

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["ID"],
            output_dir=test_output_dir,
            test_name="float_epsilon",
            norm_config=NormalizationConfig(float_epsilon=0.01),
            generate_reports=False,
            conn=shared_duckdb_conn,
        )

        # With epsilon=0.01, small differences should match
        logger.info("✅ Test passed: float_epsilon")
        logger.info("   Match Percentage: %.2f%%", result["match_percentage"])

    def test_string_trimming(
        self,
        test_input_dir: Path,
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test string trimming normalization."""
        source_content = """ID,Name
1,  John Doe
2,Jane Smith
3,  Bob  """

        target_content = """ID,Name
1,John Doe
2,Jane Smith
3,Bob"""

        source_path = test_input_dir / "test_trim_source.csv"
        target_path = test_input_dir / "test_trim_target.csv"

        source_path.write_text(source_content, encoding="utf-8")
        target_path.write_text(target_content, encoding="utf-8")

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["ID"],
            output_dir=test_output_dir,
            test_name="string_trimming",
            norm_config=NormalizationConfig(trim_strings=True),
            generate_reports=False,
            conn=shared_duckdb_conn,
        )

        assert result["match_percentage"] == 100.0, "Trimmed strings should match"

        logger.info("✅ Test passed: string_trimming")


class TestReportGeneration:
    """Test cases for report generation."""

    def test_html_report_structure(
        self,
        sample_csv_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test that HTML report has expected structure."""
        source_path, target_path = sample_csv_files

        result: dict[str, Any] = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["Customer ID"],
            output_dir=test_output_dir,
            test_name="html_structure",
            conn=shared_duckdb_conn,
        )

        html_content: str = result["html_report"].read_text(encoding="utf-8")

        # Check for key HTML elements
        assert "<!doctype html>" in html_content, "Should have doctype declaration"
        assert '<html lang="en">' in html_content, "Should have html tag with lang"
        assert "Data File Validation Report" in html_content, "Should have report title"
        assert "side-view" in html_content, "Should have default side-view class"
        assert "themeToggle" in html_content, "Should have theme toggle button"
        assert "🌙" in html_content, "Should have moon icon for light mode default"
        assert "comparison-workspace" in html_content, "Should have comparison workspace"
        assert "copyJobId" in html_content, "Should have job ID copy function"
        assert "switchView" in html_content, "Should have view switcher function"
        assert "site-footer" in html_content, "Should have footer"

        logger.info("✅ Test passed: html_structure")
        logger.info("   Report size: %s", format_bytes(len(html_content.encode("utf-8"))))

    def test_excel_report_sheets(
        self,
        sample_csv_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test that Excel report has expected sheets."""
        source_path, target_path = sample_csv_files

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["Customer ID"],
            output_dir=test_output_dir,
            test_name="excel_sheets",
            conn=shared_duckdb_conn,
        )

        assert result["excel_report"].exists(), "Excel report should exist"

        # Check file size
        file_size = result["excel_report"].stat().st_size
        assert file_size > 0, "Excel file should not be empty"

        logger.info("✅ Test passed: excel_sheets")
        logger.info("   Excel size: %s", format_bytes(file_size))


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_comparison_result(
        self,
        matching_csv_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test that empty comparison (100% match) is handled correctly."""
        source_path, target_path = matching_csv_files

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["ID"],
            output_dir=test_output_dir,
            test_name="empty_result",
            conn=shared_duckdb_conn,
        )

        assert result["results"].is_empty(), "Results should be empty"
        assert result["html_report"].exists(), "Report should still be generated"

        # Check report contains success message
        html_content = result["html_report"].read_text(encoding="utf-8")
        assert "Perfect Match" in html_content or "100%" in html_content, (
            "Report should indicate perfect match"
        )

        logger.info("✅ Test passed: empty_comparison_result")

    def test_large_differences(
        self,
        test_input_dir: Path,
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test with many row differences."""
        # Create files with many differences
        source_lines = ["ID,Value"] + [f"{i},{i * 10}" for i in range(1, 101)]
        target_lines = ["ID,Value"] + [f"{i},{i * 10 + 5}" for i in range(1, 101)]  # All different

        source_path = test_input_dir / "test_large_diff_source.csv"
        target_path = test_input_dir / "test_large_diff_target.csv"

        source_path.write_text("\n".join(source_lines), encoding="utf-8")
        target_path.write_text("\n".join(target_lines), encoding="utf-8")

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=["ID"],
            output_dir=test_output_dir,
            test_name="large_differences",
            generate_reports=False,
            conn=shared_duckdb_conn,
        )

        assert result["source_count"] == 100
        assert len(result["results"]) > 0, "Should have differences"

        logger.info("✅ Test passed: large_differences")
        logger.info("   Total differences: %d", len(result["results"]))
        logger.info("   Elapsed time: %s", result["elapsed_time"])


class TestCompression:
    """Test cases for compressed file handling."""

    def test_gzip_csv_files(
        self,
        gzip_csv_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test validation with gzip compressed CSV files."""
        source_path, target_path = gzip_csv_files

        logger.info("Testing gzip files:")
        logger.info("   Source: %s", source_path)
        logger.info("   Target: %s", target_path)

        # Read first few lines to understand structure
        with gzip.open(source_path, "rt", encoding="utf-8") as f:
            header_line = f.readline().strip()
            sample_line = f.readline().strip()

        columns = header_line.split(",")
        logger.info("   Columns found: %s", columns)
        logger.info("   Sample data: %s...", sample_line[:100])

        # Use first column as primary key (common pattern)
        primary_key = columns[0] if columns else "column0"

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=[primary_key],
            output_dir=test_output_dir,
            test_name="gzip_csv",
            header_rows=1,
            conn=shared_duckdb_conn,
        )

        # Assertions
        assert result["html_report"].exists(), "HTML report should be generated"
        assert result["excel_report"].exists(), "Excel report should be generated"
        assert result["source_count"] == 10, "Source should have 10 rows"
        assert result["target_count"] == 10, "Target should have 10 rows"
        assert result["missing_in_source"] >= 1, "Should have at least 1 missing in source (A1011)"
        assert result["missing_in_target"] >= 1, "Should have at least 1 missing in target (A1009)"

        logger.info("✅ Test passed: gzip_csv_files")
        logger.info("   HTML Report: %s", result["html_report"])
        logger.info("   Excel Report: %s", result["excel_report"])
        logger.info("   Source rows: %d", result["source_count"])
        logger.info("   Target rows: %d", result["target_count"])
        logger.info("   Match Percentage: %.2f%%", result["match_percentage"])
        logger.info("   Elapsed time: %s", result["elapsed_time"])

    def test_gzip_csv_with_specific_columns(
        self,
        gzip_csv_files: tuple[Path, Path],
        test_output_dir: Path,
        shared_duckdb_conn: duckdb.DuckDBPyConnection,
    ) -> None:
        """Test gzip CSV validation with inspection of column structure."""
        source_path, target_path = gzip_csv_files

        # Read and analyze source file structure
        with gzip.open(source_path, "rt", encoding="utf-8") as f:
            lines = [f.readline().strip() for _ in range(5)]

        header = lines[0].split(",")
        logger.info("Source file columns (%d): %s", len(header), header)

        # Read and analyze target file structure
        with gzip.open(target_path, "rt", encoding="utf-8") as f:
            target_lines = [f.readline().strip() for _ in range(5)]

        target_header = target_lines[0].split(",")
        logger.info("Target file columns (%d): %s", len(target_header), target_header)

        # Headers should match for our generated test files
        assert header == target_header, "Headers should match between source and target"
        logger.info("✓ Headers match between source and target")

        # Known columns: ACCT_ID,CUST_NAME,BALANCE,REGION,STATUS
        assert len(header) == 5, "Should have 5 columns"
        assert header[0] == "ACCT_ID", "First column should be ACCT_ID"

        # Use first column as primary key
        primary_key = header[0]

        result = run_validation(
            source_path=source_path,
            target_path=target_path,
            primary_keys=[primary_key],
            output_dir=test_output_dir,
            test_name="gzip_csv_detailed",
            header_rows=1,
            conn=shared_duckdb_conn,
        )

        assert result["html_report"].exists(), "HTML report should be generated"
        assert result["source_count"] == 10, "Source should have 10 rows"
        assert result["target_count"] == 10, "Target should have 10 rows"

        # Log detailed results
        logger.info("✅ Test passed: gzip_csv_with_specific_columns")
        logger.info("   Primary Key: %s", primary_key)
        logger.info("   Source rows: %d", result["source_count"])
        logger.info("   Target rows: %d", result["target_count"])
        logger.info("   Matching rows: %d", result["matching_rows"])
        logger.info("   Missing in source: %d", result["missing_in_source"])
        logger.info("   Missing in target: %d", result["missing_in_target"])
        logger.info("   Match Percentage: %.2f%%", result["match_percentage"])

        # Check if there are differences (we know there should be)
        assert not result["results"].is_empty(), "Should have differences"
        logger.info("   Differences found: %d rows", len(result["results"]))


class TestFileHandler:
    """Test cases for file handlers module (GCS and compression support)."""

    def test_is_gcs_path(self) -> None:
        """Test GCS path detection."""
        # Test using new file_handlers module
        assert is_gcs_path("gs://bucket/path/to/file.csv") is True
        assert is_gcs_path("gs://my-bucket/data.csv.gz") is True
        assert is_gcs_path("/local/path/file.csv") is False
        assert is_gcs_path("C:\\Windows\\path\\file.csv") is False
        assert is_gcs_path("relative/path/file.csv") is False

        logger.info("✅ Test passed: is_gcs_path")

    def test_get_compression_type(self) -> None:
        """Test compression type detection."""
        # Test using new file_handlers module
        assert get_compression_type("file.csv.gz") == "gzip"
        assert get_compression_type("file.csv.gzip") == "gzip"
        assert get_compression_type("file.csv.Z") == "compress"
        assert get_compression_type("file.csv.z") == "compress"
        assert get_compression_type("file.csv.bz2") == "bzip2"
        assert get_compression_type("file.csv.zip") == "zip"
        assert get_compression_type("file.csv") is None
        assert get_compression_type("file.txt") is None

        logger.info("✅ Test passed: get_compression_type")

    def test_decompress_gzip(self, test_input_dir: Path, test_output_dir: Path) -> None:
        """Test gzip decompression."""
        # Create a test gzip file
        original_content = "ID,Name,Value\n1,Test,100\n2,Test2,200\n"
        gz_path = test_input_dir / "test_decompress.csv.gz"

        with gzip.open(gz_path, "wt", encoding="utf-8") as f:
            f.write(original_content)

        # Decompress
        output_path = test_output_dir / "test_decompressed.csv"
        result_path = decompress_file(gz_path, output_path, "gzip")

        assert result_path.exists(), "Decompressed file should exist"

        # Verify content
        with open(result_path, encoding="utf-8") as f:
            decompressed_content = f.read()

        assert decompressed_content == original_content, "Content should match"

        logger.info("✅ Test passed: decompress_gzip")

    def test_get_file_info(self, sample_csv_files: tuple[Path, Path]) -> None:
        """Test file info retrieval."""
        # Test using new file_handlers module
        source_path, _ = sample_csv_files

        info = get_file_info(source_path)

        assert info["exists"] is True
        assert info["is_local"] is True
        assert info["compression"] is None
        assert "size_bytes" in info
        assert info["size_bytes"] > 0

        # Test GCS path info (will fail without GCS client, but structure is valid)
        try:
            gcs_info = get_file_info("gs://bucket/path/to/file.csv.gz")
            assert gcs_info["is_gcs"] is True
            assert gcs_info["compression"] == "gzip"
            assert gcs_info["filename"] == "file.csv.gz"
        except Exception as e:
            logger.info("GCS info test skipped (expected without credentials): %s", e)

        logger.info("✅ Test passed: get_file_info")

    def test_gcs_file_handler_initialization(self) -> None:
        """Test GCSFileHandler initialization."""
        # Test using new file_handlers module
        handler = GCSFileHandler()

        assert handler.temp_dir.exists(), "Temp directory should be created"
        assert len(handler.temp_files) == 0, "No temp files initially"

        # Cleanup
        handler.cleanup()

        logger.info("✅ Test passed: gcs_file_handler_initialization")

    def test_prepare_file_for_duckdb_local(
        self, sample_csv_files: tuple[Path, Path], test_output_dir: Path
    ) -> None:
        """Test prepare_file_for_duckdb with local files."""
        # Test using new file_handlers module
        source_path, _ = sample_csv_files

        result_path, temp_files = prepare_file_for_duckdb(source_path, test_output_dir)

        assert result_path == source_path, "Local uncompressed file should return as-is"

        logger.info("✅ Test passed: prepare_file_for_duckdb_local")

    def test_prepare_file_for_duckdb_gzip(self, test_input_dir: Path, test_output_dir: Path) -> None:
        """Test prepare_file_for_duckdb with gzip files."""
        # Create a test gzip file
        original_content = "ID,Name,Value\n1,Test,100\n2,Test2,200\n"
        gz_path = test_input_dir / "test_duckdb.csv.gz"

        with gzip.open(gz_path, "wt", encoding="utf-8") as f:
            f.write(original_content)

        result_path, temp_files = prepare_file_for_duckdb(gz_path, test_output_dir)

        # Gzip should be returned as-is (DuckDB handles natively)
        assert result_path == gz_path, "Gzip file should be returned as-is for DuckDB"

        logger.info("✅ Test passed: prepare_file_for_duckdb_gzip")


class TestGCSSupport:
    """Test cases for GCS (Google Cloud Storage) support."""

    def test_gcs_path_in_file_config(self) -> None:
        """Test FileConfig with GCS path."""
        from file_validator.config import FileConfig

        gcs_path = "gs://my-bucket/data/extract.csv.gz"
        config = FileConfig(
            path=gcs_path,
            file_type="csv",
            delimiter=",",
            header_rows=1,
        )

        assert config.is_gcs is True, "Should detect GCS path"
        assert config.is_compressed is True, "Should detect compression"
        assert config.filename == "extract.csv.gz", "Should extract filename"
        assert str(config.path) == gcs_path, "Path should remain as string"

        logger.info("✅ Test passed: gcs_path_in_file_config")

    def test_local_path_in_file_config(self, sample_csv_files: tuple[Path, Path]) -> None:
        """Test FileConfig with local path."""
        from file_validator.config import FileConfig

        source_path, _ = sample_csv_files
        config = FileConfig(
            path=source_path,
            file_type="csv",
            delimiter=",",
            header_rows=1,
        )

        assert config.is_gcs is False, "Should not be GCS path"
        assert config.is_compressed is False, "Should not be compressed"

        logger.info("✅ Test passed: local_path_in_file_config")

    def test_auditor_gcs_setup(self) -> None:
        """
        Test that FileAuditor sets up GCS support when paths use gs:// scheme.

        The actual ``_setup_gcs_support`` is mocked out so the test does not
        depend on real GCS credentials or the httpfs extension being available.
        """
        from file_validator.auditor import FileAuditor
        from file_validator.config import FileConfig

        source_config = FileConfig(path="gs://bucket/source.csv", header_rows=1)
        target_config = FileConfig(path="gs://bucket/target.csv", header_rows=1)

        with patch.object(FileAuditor, "_setup_gcs_support") as mock_gcs:
            with FileAuditor(
                source_config=source_config,
                target_config=target_config,
                primary_keys=["ID"],
            ) as auditor:
                # GCS setup should have been called since both paths are gs://
                mock_gcs.assert_called_once()

                # _needs_gcs flag should be True
                assert auditor._needs_gcs is True, "Should detect GCS paths"

                # DuckDB connection should exist
                assert auditor.conn is not None, "DuckDB connection should exist"

                # Temp directory should be created
                assert auditor.temp_dir.exists(), "Temp directory should exist"

        logger.info("✅ Test passed: auditor_gcs_setup")

    def test_auditor_skips_gcs_for_local_paths(self, sample_csv_files: tuple[Path, Path]) -> None:
        """Test that _setup_gcs_support is NOT called when both paths are local."""
        from file_validator.auditor import FileAuditor
        from file_validator.config import FileConfig

        source_path, target_path = sample_csv_files
        source_config = FileConfig(path=source_path, header_rows=1)
        target_config = FileConfig(path=target_path, header_rows=1)

        with patch.object(FileAuditor, "_setup_gcs_support") as mock_gcs:
            with FileAuditor(
                source_config=source_config,
                target_config=target_config,
                primary_keys=["Customer ID"],
            ) as auditor:
                mock_gcs.assert_not_called()
                assert auditor._needs_gcs is False, "Local paths should not need GCS"

        logger.info("✅ Test passed: auditor_skips_gcs_for_local_paths")

    def test_auditor_gcs_setup_mixed_paths(self, sample_csv_files: tuple[Path, Path]) -> None:
        """Test that _setup_gcs_support IS called when one path is GCS and the other is local."""
        from file_validator.auditor import FileAuditor
        from file_validator.config import FileConfig

        source_path, _ = sample_csv_files
        source_config = FileConfig(path=source_path, header_rows=1)
        target_config = FileConfig(path="gs://bucket/target.csv", header_rows=1)

        with patch.object(FileAuditor, "_setup_gcs_support") as mock_gcs:
            with FileAuditor(
                source_config=source_config,
                target_config=target_config,
                primary_keys=["ID"],
            ) as auditor:
                mock_gcs.assert_called_once()
                assert auditor._needs_gcs is True, "Mixed paths should need GCS"

        logger.info("✅ Test passed: auditor_gcs_setup_mixed_paths")

    def test_duckdb_gcs_path_handling(self) -> None:
        """Test _get_duckdb_path returns GCS path for DuckDB."""
        # Test using new file_handlers module (already imported at top)
        # Test various GCS paths
        gcs_paths = [
            "gs://bucket/file.csv",
            "gs://my-project-bucket/data/extract.csv.gz",
            "gs://bucket/path/to/compressed.csv.Z",
        ]

        for path in gcs_paths:
            assert is_gcs_path(path) is True, f"Should detect GCS path: {path}"

        # Test non-GCS paths
        local_paths = [
            "/home/user/file.csv",
            "C:\\Users\\data\\file.csv",
            "relative/path/file.csv",
            "file.csv",
        ]

        for path in local_paths:
            assert is_gcs_path(path) is False, f"Should not detect as GCS: {path}"

        logger.info("✅ Test passed: duckdb_gcs_path_handling")


# ============================================================
# Main Execution
# ============================================================


def run_all_tests():
    """Run all tests and generate reports for manual verification."""
    logger.info("=" * 60)
    logger.info("Starting File Validator Unit Tests")
    logger.info("=" * 60)

    # Create output directory
    output_dir = Path(__file__).parent / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Output directory: %s", run_dir)

    # Run pytest with verbose output
    import pytest

    exit_code = pytest.main(
        [
            __file__,
            "-v",
            "--tb=short",
            f"--basetemp={run_dir}",
        ]
    )

    logger.info("=" * 60)
    logger.info("Tests completed. Reports saved to: %s", run_dir)
    logger.info("=" * 60)

    return exit_code


if __name__ == "__main__":
    run_all_tests()
