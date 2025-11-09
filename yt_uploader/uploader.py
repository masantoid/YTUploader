"""YouTube uploader implementation using Selenium."""
from __future__ import annotations

import dataclasses
import time
from pathlib import Path
from typing import Dict, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import AccountConfig, AppConfig
from .logger import get_logger
from .session import SessionManager

logger = get_logger(__name__)


@dataclasses.dataclass
class UploadJob:
    """All information required to upload a single video."""

    account: AccountConfig
    video_path: Path
    title: str
    description: str
    tags: str
    hashtags: str
    visibility: str = "public"
    altered_content: Optional[str] = None
    kids_content: bool = False


class YouTubeUploader:
    """Handle the Selenium automation for uploading videos."""

    def __init__(self, config: AppConfig, session_manager: SessionManager) -> None:
        self.config = config
        self.session_manager = session_manager

    def _create_driver(self) -> webdriver.Chrome:
        options = Options()
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=en")
        if self.config.selenium.headless:
            options.add_argument("--headless=new")
        if self.config.selenium.user_agent:
            options.add_argument(f"--user-agent={self.config.selenium.user_agent}")
        if self.config.selenium.download_directory:
            options.add_experimental_option(
                "prefs",
                {
                    "download.default_directory": str(self.config.selenium.download_directory),
                    "download.prompt_for_download": False,
                },
            )
        if self.config.selenium.driver_path:
            driver = webdriver.Chrome(executable_path=str(self.config.selenium.driver_path), options=options)
        else:
            driver = webdriver.Chrome(options=options)
        driver.set_window_size(1280, 1024)
        return driver

    def upload(self, job: UploadJob) -> str:
        """Upload the specified job and return the resulting video URL."""

        driver = self._create_driver()
        wait = WebDriverWait(driver, 60)
        try:
            logger.info("Opening YouTube Studio for account %s", job.account.name)
            driver.get("https://studio.youtube.com")
            self.session_manager.load_cookies(driver, job.account)
            driver.get("https://studio.youtube.com")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ytcp-icon-button#create-icon")))

            create_button = driver.find_element(By.CSS_SELECTOR, "ytcp-icon-button#create-icon")
            create_button.click()
            upload_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "tp-yt-paper-item[role='menuitem']"))
            )
            upload_button.click()

            file_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']")))
            file_input.send_keys(str(job.video_path))
            logger.info("Uploading video file %s", job.video_path)

            title_box = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ytcp-social-suggestion-input[textarea]"))
            )
            title_textarea = title_box.find_element(By.ID, "textarea")
            title_textarea.clear()
            title_textarea.send_keys(job.title)

            description_box = driver.find_element(By.CSS_SELECTOR, "ytcp-mention-textbox[textarea]")
            description_textarea = description_box.find_element(By.ID, "textarea")
            description_textarea.clear()
            description_text = job.description or ""
            if job.hashtags:
                description_text = f"{description_text}\n{job.hashtags}" if description_text else job.hashtags
            description_textarea.send_keys(description_text)

            self._set_tags(driver, wait, job.tags)
            self._configure_audience(driver, wait, job.kids_content)
            self._configure_altered_content(driver, wait, job.altered_content)

            self._go_to_visibility_step(driver, wait)
            self._select_visibility(driver, wait, job.visibility)

            done_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "ytcp-button[id='done-button']"))
            )
            done_button.click()

            details_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.ytcp-video-info"))
            )
            video_url = details_button.get_attribute("href")
            if not video_url:
                raise RuntimeError("Failed to determine uploaded video URL")
            logger.info("Upload finished with video URL %s", video_url)
            return video_url
        finally:
            driver.quit()

    def _set_tags(self, driver: webdriver.Chrome, wait: WebDriverWait, tags: str) -> None:
        if not tags:
            return
        try:
            more_options = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "ytcp-button[id='toggle-button']"))
            )
            more_options.click()
        except Exception:
            logger.debug("Could not expand more options; tags field might already be visible")
        try:
            tags_box = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ytcp-free-text-chip-bar[chips]"))
            )
            tags_input = tags_box.find_element(By.ID, "chips-input")
            tags_input.send_keys(tags)
        except Exception as exc:
            logger.warning("Failed to set tags: %s", exc)

    def _configure_audience(self, driver: webdriver.Chrome, wait: WebDriverWait, kids_content: bool) -> None:
        audience_section = wait.until(
            EC.presence_of_element_located((By.NAME, "VIDEO_MADE_FOR_KIDS"))
        )
        radio_selector = "tp-yt-paper-radio-button[name='{}']".format(
            "VIDEO_MADE_FOR_KIDS_MADE_FOR_KIDS" if kids_content else "VIDEO_MADE_FOR_KIDS_NOT_MADE_FOR_KIDS"
        )
        radio_button = audience_section.find_element(By.CSS_SELECTOR, radio_selector)
        driver.execute_script("arguments[0].scrollIntoView(true);", radio_button)
        radio_button.click()

    def _configure_altered_content(
        self, driver: webdriver.Chrome, wait: WebDriverWait, altered_content: Optional[str]
    ) -> None:
        if altered_content is None:
            return
        try:
            section = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ytcp-form-checkbox[name='HAS_ALTERED_CONTENT']"))
            )
            checkbox = section.find_element(By.CSS_SELECTOR, "tp-yt-paper-checkbox")
            is_checked = "checked" in checkbox.get_attribute("class").split()
            if altered_content.lower() in {"yes", "true"} and not is_checked:
                checkbox.click()
            elif altered_content.lower() in {"no", "false"} and is_checked:
                checkbox.click()
        except Exception as exc:
            logger.warning("Could not configure altered content section: %s", exc)

    def _go_to_visibility_step(self, driver: webdriver.Chrome, wait: WebDriverWait) -> None:
        for _ in range(3):
            next_button = wait.until(EC.element_to_be_clickable((By.ID, "next-button")))
            next_button.click()
            time.sleep(1)

    def _select_visibility(self, driver: webdriver.Chrome, wait: WebDriverWait, visibility: str) -> None:
        visibility = visibility.lower()
        choices = {
            "public": "PUBLIC",
            "private": "PRIVATE",
            "unlisted": "UNLISTED",
        }
        choice = choices.get(visibility, "PUBLIC")
        selector = f"tp-yt-paper-radio-button[name='{choice}']"
        option = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
        option.click()
