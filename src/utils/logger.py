"""Standardized structured logging module with rotating file and console handlers."""
import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

DEFAULT_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "NoiseRelief",
    log_dir: Optional[Path | str] = None,
    log_level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 3,
) -> logging.Logger:
    """Configures and returns a centralized application logger.

    Args:
        name: Logger name.
        log_dir: Directory where log files are stored. Defaults to ~/.noiserelief/logs
        log_level: Logging severity level.
        max_bytes: Maximum size of a log file before rotation.
        backup_count: Number of rotated backups to keep.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(log_level)
    logger.propagate = False

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT, datefmt=DATE_FORMAT)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    if log_dir is None:
        log_dir = Path.home() / ".noiserelief" / "logs"
    else:
        log_dir = Path(log_dir)

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as ex:
        logger.warning(f"Could not initialize rotating file logger: {ex}")

    return logger


def get_logger(name: str = "NoiseRelief") -> logging.Logger:
    """Gets existing logger or sets up default if uninitialized."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger
