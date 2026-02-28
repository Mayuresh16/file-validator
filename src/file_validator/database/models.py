"""
SQLAlchemy ORM Models for File Validator

Defines database schema for jobs, reports, cache entries, and audit logs.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from file_validator import utils


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""

    pass


class JobStatus(StrEnum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """Validation job tracking and lifecycle management."""

    __tablename__ = "jobs"

    # Primary Key
    id: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)

    # Status and Progress
    status: Mapped[str] = mapped_column(
        String(20),
        default=JobStatus.PENDING,
        index=True,
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(500))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utils.utcnow, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Configuration
    source_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    target_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    primary_keys: Mapped[dict] = mapped_column(JSON, nullable=False)  # ["pk1", "pk2"]
    normalization_config: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Error Handling
    error_details: Mapped[str] = mapped_column(Text, nullable=True)

    # Indexes
    __table_args__: tuple[Index, Index] = (
        Index("idx_job_status_created", "status", "created_at"),
        Index("idx_job_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"Job(id={self.id}, status={self.status}, progress={self.progress}%)"


class Report(Base):
    """Generated report metadata and summary."""

    __tablename__ = "reports"

    # Primary Key
    id: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)

    # Foreign Key reference
    job_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    # File Paths
    html_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    excel_path: Mapped[str] = mapped_column(String(1000), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utils.utcnow, index=True)

    # Summary Statistics
    summary: Mapped[dict] = mapped_column(JSON, nullable=True)
    # {
    #   "source_count": 10000,
    #   "target_count": 10000,
    #   "matching_rows": 9995,
    #   "mismatched_rows": 5,
    #   "match_percentage": 99.95,
    #   "missing_in_source": 0,
    #   "missing_in_target": 0
    # }

    __table_args__ = (
        Index("idx_report_job_id", "job_id"),
        Index("idx_report_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"Report(id={self.id}, job_id={self.job_id})"


class CacheEntry(Base):
    """Parquet cache lifecycle management with TTL."""

    __tablename__ = "cache_entries"

    # Primary Key
    id: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)

    # Foreign Key reference
    job_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    # File Paths
    df_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    sample_df_path: Mapped[str] = mapped_column(String(1000), nullable=True)

    # Metadata
    primary_keys: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utils.utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)  # TTL expiration
    accessed_at: Mapped[datetime] = mapped_column(DateTime, default=utils.utcnow)

    __table_args__: tuple[Index, Index, Index] = (
        Index("idx_cache_job_id", "job_id"),
        Index("idx_cache_expires_at", "expires_at"),
        Index("idx_cache_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"CacheEntry(id={self.id}, job_id={self.job_id})"


class AuditLog(Base):
    """Activity audit trail for monitoring and debugging."""

    __tablename__ = "audit_logs"

    # Primary Key (auto-increment)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign Key reference
    job_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    # Action Details
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utils.utcnow, index=True)

    __table_args__: tuple[Index, Index, Index] = (
        Index("idx_audit_job_id", "job_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"AuditLog(id={self.id}, job_id={self.job_id}, action={self.action})"
