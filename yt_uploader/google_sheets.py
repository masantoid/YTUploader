"""Google Sheets integration for retrieving video metadata."""
from __future__ import annotations

import dataclasses
from typing import Dict, Iterable, List, Optional

import gspread
from google.oauth2.service_account import Credentials

from .config import AppConfig, SheetMapping
from .logger import get_logger

logger = get_logger(__name__)


@dataclasses.dataclass
class SheetRow:
    """Representation of a single Google Sheet row."""

    row_index: int
    values: Dict[str, str]

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.values.get(key, default)


class GoogleSheetClient:
    """Wrapper around gspread to fetch and update rows."""

    def __init__(self, config: AppConfig) -> None:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        credentials = Credentials.from_service_account_file(
            str(config.google.service_account_file), scopes=scopes
        )
        self.client = gspread.authorize(credentials)
        self.sheet = self.client.open_by_key(config.google.spreadsheet_id)
        self.worksheet = self.sheet.worksheet(config.google.worksheet_name)
        self.mapping = config.sheet_mapping

    def fetch_pending_row(self) -> Optional[SheetRow]:
        """Return the first row marked as ``New`` in the status column."""

        data = self.worksheet.get_all_records()
        for idx, row in enumerate(data, start=2):
            if row.get(self.mapping.status, "").strip().lower() == "new":
                logger.info("Found pending row at index %s", idx)
                return SheetRow(idx, row)
        logger.info("No pending rows found in sheet")
        return None

    def update_row_status(self, row: SheetRow, status: str, youtube_url: Optional[str] = None) -> None:
        """Update the status and optionally the YouTube URL for a row."""

        status_col = self._column_index(self.mapping.status)
        self.worksheet.update_cell(row.row_index, status_col, status)
        if youtube_url:
            url_col = self._column_index(self.mapping.youtube_url)
            self.worksheet.update_cell(row.row_index, url_col, youtube_url)

    def _column_index(self, column_name: str) -> int:
        header = self.worksheet.row_values(1)
        try:
            return header.index(column_name) + 1
        except ValueError as exc:
            raise KeyError(f"Column '{column_name}' not found in sheet header") from exc
