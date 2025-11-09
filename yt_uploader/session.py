"""Session management for Selenium drivers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from selenium.webdriver.remote.webdriver import WebDriver

from .logger import get_logger

if TYPE_CHECKING:  # pragma: no cover - used for type checking only
    from .config import AccountConfig

logger = get_logger(__name__)


class SessionManager:
    """Store and load cookies for multiple YouTube accounts."""

    def __init__(self, cookies_root: Optional[Path] = None) -> None:
        self.cookies_root = Path(cookies_root) if cookies_root else None
        if self.cookies_root:
            self.cookies_root.mkdir(parents=True, exist_ok=True)

    def cookie_file(self, account: "AccountConfig") -> Path:
        path = Path(account.cookie_file)
        if path.exists() or not self.cookies_root:
            return path
        return self.cookies_root / f"{account.name}.json"

    def save_cookies(self, driver: WebDriver, account: "AccountConfig") -> None:
        cookies = driver.get_cookies()
        path = self.cookie_file(account)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cookies, fh)
        logger.info("Saved %s cookies for account %s", len(cookies), account.name)

    def load_cookies(self, driver: WebDriver, account: "AccountConfig", domain: str = ".youtube.com") -> None:
        path = self.cookie_file(account)
        if not path.exists():
            logger.warning("Cookie file for account %s does not exist: %s", account.name, path)
            return
        with open(path, "r", encoding="utf-8") as fh:
            cookies = json.load(fh)
        driver.get("https://youtube.com")
        for cookie in cookies:
            if "sameSite" in cookie and cookie["sameSite"] == "None":
                cookie["sameSite"] = "Strict"
            try:
                driver.add_cookie(cookie)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Failed to add cookie %s: %s", cookie.get("name"), exc)
        logger.info("Loaded %s cookies for account %s", len(cookies), account.name)
