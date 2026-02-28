"""
Pytest Configuration and Fixtures

Provides shared fixtures for all tests including in-memory database,
async support, and mock data factories.
"""

from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from file_validator.config import AppSettings
from file_validator.database.config import get_async_session
from file_validator.database.models import Base


# ============================================================================
# CONFIGURATION FIXTURES
# ============================================================================


@pytest.fixture
def app_settings():
    """Provide test application settings with in-memory SQLite."""
    return AppSettings(
        server=AppSettings.ServerSettings(
            host="127.0.0.1",
            port=8000,
            environment="test",
            debug=True,
            log_level="DEBUG",
        ),
        database=AppSettings.DatabaseSettings(
            database_url="sqlite+aiosqlite:///:memory:",
            echo=False,
            pool_size=1,
            max_overflow=0,
        ),
        cache=AppSettings.CacheSettings(),
        duckdb=AppSettings.DuckDBSettings(),
    )


# ============================================================================
# DATABASE FIXTURES
# ============================================================================


@pytest_asyncio.fixture
async def async_engine(app_settings):
    """Create in-memory SQLite engine for tests."""
    engine = create_async_engine(
        app_settings.database.database_url,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(async_engine):
    """Create async database session for tests."""
    factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def session_factory(async_engine):
    """Create session factory for tests."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================


@pytest.fixture
def test_files_dir():
    """Path to test input files."""
    test_dir = Path(__file__).parent / "fixtures" / "sample_files"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture
def test_source_csv(test_files_dir):
    """Create test source CSV file."""
    source_file = test_files_dir / "test_source.csv"

    if not source_file.exists():
        # Create sample test data
        source_file.write_text(
            """id,name,value,date
1,John,100.50,2026-01-01
2,Jane,200.75,2026-01-02
3,Bob,150.25,2026-01-03
"""
        )

    return source_file


@pytest.fixture
def test_target_csv(test_files_dir):
    """Create test target CSV file."""
    target_file = test_files_dir / "test_target.csv"

    if not target_file.exists():
        # Create sample test data (with slight differences)
        target_file.write_text(
            """id,name,value,date
1,John,100.50,2026-01-01
2,Jane,200.75,2026-01-02
3,Robert,150.25,2026-01-03
4,Alice,300.00,2026-01-04
"""
        )

    return target_file


@pytest.fixture
def sample_validation_config() -> dict:
    """Provide sample validation configuration."""
    return {
        "job_name": "test_job",
        "source_path": "/path/to/source.csv",
        "target_path": "/path/to/target.csv",
        "primary_keys": ["id"],
        "file_type": "csv",
        "delimiter": ",",
        "encoding": "utf-8",
        "compression": None,
        "header_rows": 0,
        "trailer_patterns": [],
        "normalization": {
            "float_epsilon": None,
            "normalize_dates": False,
            "trim_strings": False,
            "treat_null_as_empty": True,
        },
    }


# ============================================================================
# UTILITY FIXTURES
# ============================================================================


@pytest.fixture
def temp_dir(tmp_path):
    """Provide temporary directory for test files."""
    return tmp_path


@pytest.fixture
def cleanup_files(tmp_path) -> callable:
    """Fixture to cleanup test files after test."""
    files_to_cleanup: list[Path] = []

    def add_file(filepath: str | Path) -> None:
        files_to_cleanup.append(Path(filepath))

    yield add_file

    # Cleanup
    for filepath in files_to_cleanup:
        if filepath.exists():
            filepath.unlink()


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow")
    config.addinivalue_line("markers", "unit: mark test as unit test")


# ============================================================================
# PYTEST HOOKS
# ============================================================================


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Add test information to report."""
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call" and rep.outcome == "failed":
        # Print additional debug info on failure
        print(f"\n📋 Test: {item.name}")
        print(f"📁 File: {item.fspath}")
