"""Scheduling helper for repeated uploads."""
from __future__ import annotations

import datetime as dt
import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List

from dateutil import tz

from .config import AppConfig
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScheduledTask:
    timestamp: dt.datetime
    callback: Callable[[], None]


class UploadScheduler:
    """Simple scheduler that runs callbacks at configured times."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, callback: Callable[[], None]) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, args=(callback,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join()
            self._thread = None

    def _run(self, callback: Callable[[], None]) -> None:
        while not self._stop_event.is_set():
            now = dt.datetime.now(dt.timezone.utc)
            next_times = list(self._next_run_times(now.date()))
            if not next_times:
                logger.warning("No schedule configured; sleeping for one hour")
                time.sleep(3600)
                continue
            upcoming = [t for t in next_times if t >= now]
            if not upcoming:
                tomorrow = now.date() + dt.timedelta(days=1)
                upcoming = list(self._next_run_times(tomorrow))
            if not upcoming:
                logger.error("No upcoming schedule slots found; sleeping for one hour")
                time.sleep(3600)
                continue
            next_run = min(upcoming)
            delay = (next_run - now).total_seconds()
            logger.info("Next upload scheduled at %s (in %.0f seconds)", next_run.isoformat(), delay)
            if delay > 0:
                self._stop_event.wait(timeout=delay)
            if self._stop_event.is_set():
                break
            try:
                callback()
            except Exception as exc:  # pragma: no cover - runtime safety
                logger.exception("Scheduled task failed: %s", exc)

    def _next_run_times(self, day: dt.date) -> Iterable[dt.datetime]:
        times = list(self.config.scheduled_datetimes(day))
        if self.config.schedule.randomize:
            random.shuffle(times)
        return times
