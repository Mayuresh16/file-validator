"""
Database Repository Pattern for CRUD Operations

Provides async-safe data access layer for Job, Report, and Cache entities.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from file_validator import utils, AppSettings
from file_validator.config import get_settings
from file_validator.database.models import (
    AuditLog,
    CacheEntry,
    Job,
    JobStatus,
    Report,
)

logger = logging.getLogger(__name__)


class JobRepository:
    """Repository for Job entity - handles all job-related database operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize JobRepository with async session.

        Args:
            session: SQLAlchemy AsyncSession instance
        """
        self.session = session

    async def create_job(
        self,
        job_id: str,
        source_path: str,
        target_path: str,
        primary_keys: list[str],
        normalization_config: dict | None = None,
    ) -> Job:
        """
        Create new validation job.

        Args:
            job_id: Unique job identifier
            source_path: Path to source file
            target_path: Path to target file
            primary_keys: List of primary key column names
            normalization_config: Optional normalization settings

        Returns:
            Job: Created job instance
        """
        job = Job(
            id=job_id,
            status=JobStatus.PENDING.value,
            progress=0,
            message="Job created",
            source_path=source_path,
            target_path=target_path,
            primary_keys=primary_keys,
            normalization_config=normalization_config,
        )
        self.session.add(job)
        await self.session.commit()
        logger.info("Job created: %s", job_id)
        return job

    async def get_job(self, job_id: str) -> Job | None:
        """
        Retrieve job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job: Job instance or None if not found
        """
        result = await self.session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def update_job_progress(
        self,
        job_id: str,
        progress: int,
        message: str,
        status: str | None = None,
    ) -> None:
        """
        Update job progress and status.

        Args:
            job_id: Job identifier
            progress: Progress percentage (0-100)
            message: Status message
            status: Optional job status
        """
        update_data: dict[Any, int | str] = {
            Job.progress: progress,
            Job.message: message,
        }
        if status:
            update_data[Job.status] = status

        await self.session.execute(update(Job).where(Job.id == job_id).values(**update_data))
        await self.session.commit()
        logger.debug("Job %s progress: %d%% - %s", job_id, progress, message)

    async def mark_job_running(self, job_id: str) -> None:
        """Mark job as running and set started_at timestamp."""
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.RUNNING.value,
                started_at=utils.utcnow(),
            )
        )
        await self.session.commit()
        logger.info("Job %s marked as running", job_id)

    async def complete_job(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        """
        Mark job as completed or failed.

        Args:
            job_id: Job identifier
            status: Final status (completed or failed)
            error: Optional error message if failed
        """
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=status,
                completed_at=utils.utcnow(),
                error_details=error,
            )
        )
        await self.session.commit()
        logger.info("Job %s completed with status: %s", job_id, status)

    async def list_recent_jobs(self, limit: int = 10) -> list[Job]:
        """
        List recent jobs ordered by creation date.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            list[Job]: Recent jobs
        """
        result = await self.session.execute(select(Job).order_by(desc(Job.created_at)).limit(limit))
        return result.scalars().all()

    async def list_pending_jobs(self) -> list[Job]:
        """List all pending jobs."""
        result = await self.session.execute(select(Job).where(Job.status == JobStatus.PENDING.value))
        return result.scalars().all()

    async def delete_job(self, job_id: str) -> None:
        """Delete a job."""
        await self.session.execute(delete(Job).where(Job.id == job_id))
        await self.session.commit()
        logger.info("Job %s deleted", job_id)


class ReportRepository:
    """Repository for Report entity - handles report metadata."""

    def __init__(self, session: AsyncSession):
        """Initialize ReportRepository with async session."""
        self.session: AsyncSession = session

    async def create_report(
        self,
        report_id: str,
        job_id: str,
        html_path: str,
        summary: dict[str, int] | None = None,
    ) -> Report:
        """
        Create new report record.

        Args:
            report_id: Unique report identifier
            job_id: Associated job identifier
            html_path: Path to generated HTML report
            summary: Optional summary statistics dictionary

        Returns:
            Report: Created report instance
        """
        report = Report(
            id=report_id,
            job_id=job_id,
            html_path=html_path,
            summary=summary,
        )
        self.session.add(report)
        await self.session.commit()
        logger.info("Report created: %s", report_id)
        return report

    async def get_report(self, report_id: str) -> Optional[Report]:
        """Get report by ID."""
        result = await self.session.execute(select(Report).where(Report.id == report_id))
        return result.scalar_one_or_none()

    async def update_report(
        self,
        report_id: str,
        excel_path: str | None = None,
        summary: dict | None = None,
    ) -> None:
        """Update report with Excel path and/or summary."""
        update_data = {}
        if excel_path:
            update_data[Report.excel_path] = excel_path
        if summary:
            update_data[Report.summary] = summary

        await self.session.execute(update(Report).where(Report.id == report_id).values(**update_data))
        await self.session.commit()

    async def list_recent_reports(self, limit: int = 10) -> list[Report]:
        """List recent reports."""
        result = await self.session.execute(select(Report).order_by(desc(Report.created_at)).limit(limit))
        return result.scalars().all()


class CacheRepository:
    """Repository for CacheEntry entity - manages parquet cache lifecycle."""

    def __init__(self, session: AsyncSession):
        """Initialize CacheRepository with async session."""
        self.session = session

    async def create_cache_entry(
        self,
        job_id: str,
        df_path: str,
        sample_df_path: Optional[str] = None,
        primary_keys: Optional[list[str]] = None,
    ) -> CacheEntry:
        """
        Create cache entry with TTL.

        Args:
            job_id: Associated job identifier
            df_path: Path to parquet results file
            sample_df_path: Optional path to parquet sample file
            primary_keys: Optional primary key list

        Returns:
            CacheEntry: Created cache entry
        """
        settings: AppSettings = get_settings()
        expires_at: datetime = utils.utcnow() + timedelta(seconds=settings.cache.ttl_seconds)

        entry = CacheEntry(
            id=job_id,
            job_id=job_id,
            df_path=df_path,
            sample_df_path=sample_df_path,
            primary_keys=primary_keys,
            expires_at=expires_at,
        )
        self.session.add(entry)
        await self.session.commit()
        logger.info("Cache entry created: %s (expires at %s)", job_id, expires_at)
        return entry

    async def get_cache_entry(self, job_id: str) -> CacheEntry | None:
        """Get cache entry by job ID."""
        result = await self.session.execute(select(CacheEntry).where(CacheEntry.id == job_id))
        return result.scalar_one_or_none()

    async def update_accessed_time(self, job_id: str) -> None:
        """Update accessed_at timestamp for cache entry."""
        await self.session.execute(
            update(CacheEntry).where(CacheEntry.id == job_id).values(accessed_at=utils.utcnow())
        )
        await self.session.commit()

    async def cleanup_expired_cache(self) -> int:
        """
        Delete expired cache entries.

        Returns:
            int: Number of entries deleted
        """
        result = await self.session.execute(delete(CacheEntry).where(CacheEntry.expires_at < utils.utcnow()))
        await self.session.commit()
        deleted_count = result.rowcount
        logger.info("Cleaned up %d expired cache entries", deleted_count)
        return deleted_count

    async def list_cache_entries(self) -> list[CacheEntry]:
        """List all cache entries."""
        result = await self.session.execute(select(CacheEntry))
        return result.scalars().all()

    async def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        entries = await self.list_cache_entries()
        total_bytes = sum(1 for _ in entries)  # Simplified - actual would sum file sizes
        return {
            "total_entries": len(entries),
            "total_bytes": total_bytes,
            "expired_count": len([e for e in entries if e.expires_at < utils.utcnow()]),
        }


class AuditLogRepository:
    """Repository for AuditLog entity - activity tracking."""

    def __init__(self, session: AsyncSession):
        """Initialize AuditLogRepository with async session."""
        self.session = session

    async def log_action(
        self,
        job_id: str,
        action: str,
        details: dict | None = None,
    ) -> AuditLog:
        """
        Create audit log entry.

        Args:
            job_id: Associated job identifier
            action: Action description
            details: Optional action details

        Returns:
            AuditLog: Created audit log entry
        """
        log_entry = AuditLog(
            job_id=job_id,
            action=action,
            details=details,
        )
        self.session.add(log_entry)
        await self.session.commit()
        logger.debug("Audit log: %s - %s", job_id, action)
        return log_entry

    async def get_job_audit_log(self, job_id: str) -> list[AuditLog]:
        """Get all audit logs for a job."""
        result = await self.session.execute(
            select(AuditLog).where(AuditLog.job_id == job_id).order_by(desc(AuditLog.created_at))
        )
        return result.scalars().all()
