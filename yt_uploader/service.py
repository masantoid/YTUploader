"""Reusable backend helpers for CLI and GUI entry points."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import AppConfig, load_config
from .logger import setup_logging
from .main import UploadController
from .scheduler import UploadScheduler


class UploaderService:
    """High level service wrapper used by the GUI to control the uploader."""

    def __init__(self) -> None:
        self._config: Optional[AppConfig] = None
        self._config_path: Optional[Path] = None
        self._controller: Optional[UploadController] = None
        self._scheduler: Optional[UploadScheduler] = None
        self._running = False

    @property
    def config_path(self) -> Optional[Path]:
        return self._config_path

    @property
    def is_running(self) -> bool:
        return self._running

    def load_config(self, path: Path) -> AppConfig:
        config = load_config(path)
        self._config = config
        self._config_path = Path(path)
        return config

    def start(self) -> None:
        if not self._config or not self._config_path:
            raise RuntimeError("Konfigurasi belum dimuat")
        if self._running:
            return
        setup_logging(self._config.cleanup.log_directory, self._config.cleanup.retention_days)
        self._controller = UploadController(self._config)
        self._scheduler = UploadScheduler(self._config)
        self._scheduler.start(self._controller.run_once)
        self._running = True

    def stop(self) -> None:
        if self._scheduler:
            self._scheduler.stop()
        self._controller = None
        self._scheduler = None
        self._running = False

