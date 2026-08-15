import json
import os
import sys
from pathlib import Path

DEAFAULT_SETTINGS = {
    "format": "bv*+ba/b",
    "output_template": "%(title)s.%(ext)s",
    "download_playlist": False,
    "use_browser_cookies": True,
    "browser": "chrome",
    "browser_profile": None,
    "verbose": False,
}

class SettingsManager:
    def __init__(self):
        self.settings_path = self._get_settings_path()
        self.settings = DEAFAULT_SETTINGS.copy()
        self.load()

    @staticmethod
    def _get_settings_path() -> Path:
        pass

    def load(self) -> None:
        pass

    def save(self) -> None:
        pass

    def get(self, key: str, default=None):
        return self.settings.get(key, default)

    def set(self, key: str, value) -> None:
        pass

    def reset(self) -> None:
        self.settings = DEAFAULT_SETTINGS.copy()
        self.save()

    def build_ydl_options(self) -> dict:
        pass

    