"""Logging helpers for the uploader application."""
from __future__ import annotations

import logging
import logging.handlers
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def setup_logging(log_dir: Path, retention_days: int = 1) -> logging.Logger:
    """Create and configure the application logger."""

    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("yt_uploader")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)

    logfile = log_dir / "uploader.log"
    handler = logging.handlers.TimedRotatingFileHandler(
        logfile, when="midnight", backupCount=retention_days
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    cleanup_old_logs(log_dir, retention_days)
    logger.debug("Logging initialised. Writing to %s", logfile)
    return logger


def cleanup_old_logs(log_dir: Path, retention_days: int) -> None:
    """Delete log files that are older than the retention period."""

    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    for path in log_dir.glob("*.log*"):
        if datetime.utcfromtimestamp(path.stat().st_mtime) < cutoff:
            try:
                path.unlink()
            except OSError:
                pass


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Convenience wrapper around :func:`logging.getLogger`."""

    return logging.getLogger(name or "yt_uploader")
