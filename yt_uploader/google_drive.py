"""Utilities for interacting with Google Drive files."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests

from .logger import get_logger

logger = get_logger(__name__)


class GoogleDriveDownloader:
    """Download files from Google Drive using direct links or file ids."""

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

    def download(self, *, file_id: Optional[str] = None, download_url: Optional[str] = None, destination: Path) -> Path:
        """Download a file either by ID or direct URL."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        if download_url:
            logger.info("Downloading video from direct link: %s", download_url)
            response = self.session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            with open(destination, "wb") as fh:
                for chunk in response.iter_content(chunk_size=1048576):
                    if chunk:
                        fh.write(chunk)
            return destination
        if not file_id:
            raise ValueError("Either file_id or download_url must be provided")
        logger.info("Downloading video from Google Drive file id: %s", file_id)
        url = "https://drive.google.com/uc?export=download"
        params = {"id": file_id}
        response = self.session.get(url, params=params, stream=True, timeout=60)
        response.raise_for_status()
        confirmation_token = self._get_confirm_token(response)
        if confirmation_token:
            params["confirm"] = confirmation_token
            response = self.session.get(url, params=params, stream=True, timeout=60)
            response.raise_for_status()
        with open(destination, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1048576):
                if chunk:
                    fh.write(chunk)
        return destination

    @staticmethod
    def _get_confirm_token(response: requests.Response) -> Optional[str]:
        for key, value in response.cookies.items():
            if key.startswith("download_warning"):
                return value
        return None
