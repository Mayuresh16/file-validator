"""File Validator - Production-grade file validation and comparison platform."""

__version__ = "0.2.0"
__author__ = "Mayuresh Kedari"

from file_validator.config import get_settings, reset_settings, AppSettings
from file_validator.logging_config import setup_logging, get_logger
from file_validator.exceptions import FileValidatorException

__all__ = [
    "get_settings",
    "reset_settings",
    "AppSettings",
    "setup_logging",
    "get_logger",
    "FileValidatorException",
]
