from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from yt_dlp import SUPPORTED_BROWSERS


class CookieMode(Enum):
    NONE = "none"
    BROWSER = "browser"
    FILE = "file"

    SUPPORTED_BROWSERS = {
        "chrome",
        "firefox",
        "edge",
        "brave",
        "chromium",
        "opera",
        "safari",
        "vivaldi",
    }

@dataclass
class CookieSettings:
    mode: CookieMode = CookieMode.NONE
    browser: str | None = None
    profile: str | None = None
    cookie_file: Path | None = None


class CookieManager:
    def __init__(self, settings: CookieSettings):
        self.settings = settings

    def get_yt_dlp_options(self) -> dict:
        if self.settings.mode == CookieMode.NONE:
            return {}

        if self.settings.mode == CookieMode.BROWSER:
            return self._get_browser_options()

        if self. settings.mode == CookieMode.FILE:
            return self._get_file_options()

        raise ValueError("Неизвестный режим работы с cookies!")

    def _get_browser_options(self) -> dict:
        browser = (self.settings.browser or "").lower()

        if browser not in SUPPORTED_BROWSERS:
            raise ValueError(f"Браузер не поддерживается: {browser}")

        if self.settings.profile:
            cookies_from_browser = {
                browser,
                self.settings.profile,
                None,
                None,
            }
        else:
            cookies_from_browser = (browser,)

        return {
            "cookiesfrombrowser": cookies_from_browser
        }

    def _get_file_options(self) -> dict:
        if self.settings.cookie_file is None:
            raise ValueError("Не указан файл cookies!")

        cookie_file = self.settings.cookie_file.expanduser().resolve()

        if not cookie_file.is_file():
            raise FileNotFoundError(f"Файл cookies не найден: {cookie_file}")

        self._validate_cookie_file(cookie_file)

        return{
            "cookiefile": str(cookie_file)
        }

    @staticmethod
    def _validate_cookie_file(path: Path) -> None:
        with path.open(
            "r",
            encoding="utf-8-sig",
            errors="replace",
        ) as file:
            first_line = file.readline.strip()

            allowed_headers = {
                "# Netscape HTTP Cookie File",
                "# HTTP Cookie File",
            }

            if first_line not in allowed_headers:
                raise ValueError(
                    "Файл должен иметь формат Netscape cookies.txt"
                )