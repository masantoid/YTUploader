"""Entry point for the YouTube uploader."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from .config import AccountConfig, AppConfig, load_config
from .google_drive import GoogleDriveDownloader
from .google_sheets import GoogleSheetClient
from .logger import get_logger, setup_logging
from .scheduler import UploadScheduler
from .session import SessionManager
from .uploader import UploadJob, YouTubeUploader

logger = get_logger(__name__)


class UploadController:
    """High level coordination for retrieving sheet data and uploading videos."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.sheet_client = GoogleSheetClient(config)
        self.session_manager = SessionManager()
        self.uploader = YouTubeUploader(config, self.session_manager)
        self.drive_downloader = GoogleDriveDownloader()
        self._account_index = 0

    def run_once(self) -> None:
        row = self.sheet_client.fetch_pending_row()
        if not row:
            logger.info("No pending uploads found. Nothing to do.")
            return

        account = self._resolve_account()
        self.sheet_client.update_row_status(row, "Processing")

        try:
            video_file = self._prepare_video(row)
            job = self._build_job(row, account, video_file)
        except Exception as exc:
            logger.exception("Failed to prepare upload job: %s", exc)
            self.sheet_client.update_row_status(row, "Failed")
            return

        for attempt in range(1, self.config.max_retries + 1):
            try:
                video_url = self.uploader.upload(job)
                self.sheet_client.update_row_status(row, "Done", youtube_url=video_url)
                logger.info("Upload successful: %s", video_url)
                if self.config.cleanup.remove_uploaded_videos:
                    try:
                        video_file.unlink()
                    except FileNotFoundError:
                        logger.debug("Video file already removed: %s", video_file)
                return
            except Exception as exc:
                logger.exception("Upload attempt %s failed: %s", attempt, exc)
                if attempt < self.config.max_retries:
                    logger.info("Retrying upload in %s seconds", self.config.retry_interval_seconds)
                    time.sleep(self.config.retry_interval_seconds)
                else:
                    logger.error("All upload attempts failed for %s", video_file)
                    self.sheet_client.update_row_status(row, "Failed")

    def _prepare_video(self, row) -> Path:
        filename = row.get(self.config.sheet_mapping.filename)
        if not filename:
            raise ValueError("Video filename is missing from sheet row")
        local_path = Path(filename)
        if local_path.exists():
            logger.info("Using local video file %s", local_path)
            return local_path
        download_dir = Path("downloads")
        download_dir.mkdir(parents=True, exist_ok=True)
        destination = download_dir / Path(filename).name
        drive_file_id = row.get(self.config.sheet_mapping.drive_file_id or "")
        drive_download_url = row.get(self.config.sheet_mapping.drive_download_url or "")
        if drive_download_url:
            self.drive_downloader.download(download_url=drive_download_url, destination=destination)
        elif drive_file_id:
            self.drive_downloader.download(file_id=drive_file_id, destination=destination)
        else:
            raise FileNotFoundError(
                f"Video file {filename} not found locally and no Google Drive reference provided"
            )
        return destination

    def _build_job(self, row, account: "AccountConfig", video_file: Path) -> UploadJob:
        mapping = self.config.sheet_mapping
        altered_value = None
        if mapping.altered_content:
            raw_altered = row.get(mapping.altered_content)
            if raw_altered is not None:
                text = str(raw_altered).strip()
                if text:
                    altered_value = text

        kids_value = False
        if mapping.made_for_kids:
            raw_kids = row.get(mapping.made_for_kids)
            if raw_kids is not None:
                kids_value = str(raw_kids).strip().lower() in {"yes", "true", "1"}

        return UploadJob(
            account=account,
            video_path=video_file,
            title=row.get(mapping.title, ""),
            description=row.get(mapping.description, ""),
            tags=row.get(mapping.tags, ""),
            hashtags=row.get(mapping.hashtags, ""),
            altered_content=altered_value,
            kids_content=kids_value,
        )

    def _resolve_account(self) -> AccountConfig:
        if not self.config.accounts:
            raise RuntimeError("No accounts configured")
        # Rotate accounts sequentially to spread usage evenly across configured profiles.
        account = self.config.accounts[self._account_index % len(self.config.accounts)]
        self._account_index += 1
        logger.info("Using account %s for upload", account.name)
        return account


def run(config_path: Path) -> None:
    config = load_config(config_path)
    setup_logging(config.cleanup.log_directory, config.cleanup.retention_days)
    controller = UploadController(config)

    scheduler = UploadScheduler(config)
    scheduler.start(controller.run_once)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping scheduler")
        scheduler.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated YouTube uploader")
    parser.add_argument("config", type=Path, help="Path to configuration YAML file")
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
