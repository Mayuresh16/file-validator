"""
File Validator Application Configuration

Uses Pydantic Settings v2 for environment-aware configuration.
Priority: environment variables > .env file > defaults

Usage:
    from file_validator.config import get_settings
    settings = get_settings()
    db_url = settings.database.database_url
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration - supports SQLite (dev) or PostgreSQL (prod)."""

    database_url: str = Field(
        default="sqlite:///./file_validator.db",
        description="SQLAlchemy database URL. Change to postgresql+asyncpg://... for PostgreSQL",
    )
    echo: bool = Field(default=False, description="Log all SQL queries")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Max overflow connections")

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        case_sensitive=False,
        env_file=".env",
    )


class ServerSettings(BaseSettings):
    """FastAPI server configuration."""

    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, description="Server port")
    environment: Literal["dev", "prod"] = Field(default="dev", description="Environment type")
    debug: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    model_config = SettingsConfigDict(
        env_prefix="SERVER_",
        case_sensitive=False,
    )


class CacheSettings(BaseSettings):
    """Caching and TTL configuration."""

    cache_dir: Path = Field(default=Path("./reports/_cache"))
    ttl_seconds: int = Field(default=12 * 60 * 60, description="Cache TTL: 12 hours")
    cleanup_interval: int = Field(default=1 * 60 * 60, description="Cleanup interval: 1 hour")
    max_cache_size_mb: int = Field(default=5000, description="Max total cache size")

    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        case_sensitive=False,
    )


class DuckDBSettings(BaseSettings):
    """DuckDB tuning parameters."""

    memory_limit: str = Field(default="6GB")
    threads: int = Field(default=4)
    preserve_insertion_order: bool = Field(default=False)
    allocator_flush_threshold: str = Field(default="256MB")

    model_config = SettingsConfigDict(
        env_prefix="DUCKDB_",
        case_sensitive=False,
    )


class AppSettings(BaseSettings):
    """Complete application settings - top-level configuration."""

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    duckdb: DuckDBSettings = Field(default_factory=DuckDBSettings)

    # File upload limits
    max_upload_size_mb: int = Field(default=5000)
    upload_dir: Path = Field(default=Path("./uploads"))

    # Report settings
    reports_dir: Path = Field(default=Path("./reports"))

    # GCS settings
    gcs_credentials_path: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_nested_delimiter="__",
    )


# Global settings instance
_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """
    Get or initialize global settings.

    Returns:
        AppSettings: Application configuration instance

    Examples:
        >>> settings = get_settings()
        >>> db_url = settings.database.database_url
        >>> log_level = settings.server.log_level
    """
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


def reset_settings() -> None:
    """Reset global settings instance (for testing)."""
    global _settings
    _settings = None
