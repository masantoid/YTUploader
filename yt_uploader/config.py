"""Configuration utilities for the YouTube uploader application."""
from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import yaml


@dataclasses.dataclass
class AccountConfig:
    """Configuration for a single YouTube account."""

    name: str
    cookie_file: Path
    channel_url: Optional[str] = None

    def __post_init__(self) -> None:
        self.cookie_file = Path(self.cookie_file)


@dataclasses.dataclass
class SheetMapping:
    """Mapping of Google Sheet column names to uploader fields."""

    title: str
    description: str
    hashtags: str
    tags: str
    filename: str
    drive_file_id: Optional[str] = None
    drive_download_url: Optional[str] = None
    drive_view_url: Optional[str] = None
    created_time: Optional[str] = None
    final_output: Optional[str] = None
    status: str = "UploadYT"
    youtube_url: str = "YTUrl"
    altered_content: Optional[str] = None
    made_for_kids: Optional[str] = None


@dataclasses.dataclass
class ScheduleConfig:
    """Configuration describing how uploads are scheduled."""

    times: Sequence[str]
    randomize: bool = False
    timezone: str = "UTC"


@dataclasses.dataclass
class SeleniumConfig:
    """Configuration for the Selenium WebDriver."""

    driver_path: Optional[Path] = None
    headless: bool = True
    user_agent: Optional[str] = None
    download_directory: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.driver_path:
            self.driver_path = Path(self.driver_path)
        if self.download_directory:
            self.download_directory = Path(self.download_directory)


@dataclasses.dataclass
class GoogleConfig:
    """Configuration for Google integrations."""

    service_account_file: Path
    spreadsheet_id: str
    worksheet_name: str

    def __post_init__(self) -> None:
        self.service_account_file = Path(self.service_account_file)


@dataclasses.dataclass
class CleanupConfig:
    """Configuration for log retention and uploaded file cleanup."""

    log_directory: Path = Path("logs")
    retention_days: int = 1
    remove_uploaded_videos: bool = True

    def __post_init__(self) -> None:
        self.log_directory = Path(self.log_directory)


@dataclasses.dataclass
class AppConfig:
    """Top level configuration for the application."""

    accounts: List[AccountConfig]
    google: GoogleConfig
    sheet_mapping: SheetMapping
    schedule: ScheduleConfig
    selenium: SeleniumConfig = dataclasses.field(default_factory=SeleniumConfig)
    cleanup: CleanupConfig = dataclasses.field(default_factory=CleanupConfig)
    max_retries: int = 3
    retry_interval_seconds: int = 30

    @classmethod
    def from_file(cls, path: Path | str) -> "AppConfig":
        path = Path(path)
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return cls.from_dict(data, base_path=path.parent)

    @classmethod
    def from_dict(cls, data: dict, base_path: Path | None = None) -> "AppConfig":
        def resolve_path(value: Optional[str | Path]) -> Optional[Path]:
            if value is None:
                return None
            path = Path(value)
            if not path.is_absolute() and base_path is not None:
                path = base_path / path
            return path

        accounts = []
        for account in data.get("accounts", []):
            cookie_file = resolve_path(account.get("cookie_file"))
            if cookie_file:
                account = {**account, "cookie_file": cookie_file}
            accounts.append(AccountConfig(**account))

        google_data = data["google"].copy()
        google_data["service_account_file"] = resolve_path(google_data.get("service_account_file"))
        google = GoogleConfig(**google_data)
        sheet_mapping = SheetMapping(**data["sheet_mapping"])
        schedule = ScheduleConfig(**data["schedule"])
        selenium_data = data.get("selenium", {}).copy()
        if "driver_path" in selenium_data:
            selenium_data["driver_path"] = resolve_path(selenium_data.get("driver_path"))
        if "download_directory" in selenium_data:
            selenium_data["download_directory"] = resolve_path(selenium_data.get("download_directory"))
        selenium = SeleniumConfig(**selenium_data)

        cleanup_data = data.get("cleanup", {}).copy()
        if "log_directory" in cleanup_data:
            cleanup_data["log_directory"] = resolve_path(cleanup_data.get("log_directory"))
        cleanup = CleanupConfig(**cleanup_data)
        return cls(
            accounts=accounts,
            google=google,
            sheet_mapping=sheet_mapping,
            schedule=schedule,
            selenium=selenium,
            cleanup=cleanup,
            max_retries=data.get("max_retries", 3),
            retry_interval_seconds=data.get("retry_interval_seconds", 30),
        )

    def scheduled_datetimes(self, day: dt.date) -> Iterable[dt.datetime]:
        from dateutil import tz

        timezone = tz.gettz(self.schedule.timezone)
        for time_str in self.schedule.times:
            hour, minute = [int(part) for part in time_str.split(":", 1)]
            dt_local = dt.datetime.combine(day, dt.time(hour=hour, minute=minute, tzinfo=timezone))
            yield dt_local.astimezone(tz.UTC)


def load_config(path: Path | str) -> AppConfig:
    """Load the application configuration from a YAML file."""

    return AppConfig.from_file(path)
