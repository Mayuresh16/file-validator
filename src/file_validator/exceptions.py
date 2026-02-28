"""
Custom Exceptions for File Validator

Provides application-specific exceptions with proper error handling.
"""


class FileValidatorException(Exception):
    """Base exception for all File Validator errors."""

    pass


class ConfigurationError(FileValidatorException):
    """Raised when configuration is invalid."""

    pass


class JobNotFoundError(FileValidatorException):
    """Raised when a job is not found."""

    pass


class ValidationFailedError(FileValidatorException):
    """Raised when validation fails."""

    pass


class CacheError(FileValidatorException):
    """Raised when cache operation fails."""

    pass


class UploadError(FileValidatorException):
    """Raised when file upload fails."""

    pass


class DatabaseError(FileValidatorException):
    """Raised when database operation fails."""

    pass


class FileNotFoundError(FileValidatorException):
    """Raised when file is not found."""

    pass


class InvalidFileFormatError(FileValidatorException):
    """Raised when file format is invalid."""

    pass


class AsyncOperationError(FileValidatorException):
    """Raised when async operation fails."""

    pass
