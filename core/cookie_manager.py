# Работа с cookies.
# Модуль преобразует пользовательские настройки cookies в словарь опций yt-dlp.
# Cookies позволяют скачивать видео, доступные только авторизованному
# пользователю (возрастные ограничения, закрытые плейлисты), и снижают риск
# проверки "подтвердите, что вы не бот".
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Браузеры, из которых yt-dlp умеет читать cookies. Набор определен на уровне
# модуля, а не внутри Enum: атрибут класса Enum становится членом перечисления,
# а не обычной константой.
SUPPORTED_BROWSERS = {
    "chrome", "firefox", "edge", "brave",
    "chromium", "opera", "safari", "vivaldi",
}


class CookieMode(Enum):
    """Способ получения cookies."""
    NONE = "none"        # cookies не используются
    BROWSER = "browser"  # чтение из профиля установленного браузера
    FILE = "file"        # чтение из файла cookies.txt (формат Netscape)


@dataclass
class CookieSettings:
    """
    Контейнер с настройками cookies. Не содержит логики и используется
    для передачи данных между окном, потоками и менеджером.

    browser     - название браузера (для режима BROWSER)
    profile     - имя профиля браузера; None означает профиль по умолчанию
    cookie_file - путь к файлу cookies.txt (для режима FILE)
    """
    mode: CookieMode = CookieMode.NONE
    browser: str | None = None
    profile: str | None = None
    cookie_file: Path | None = None


class CookieManager:
    """Формирует опции yt-dlp на основе CookieSettings."""

    def __init__(self, settings: CookieSettings):
        self.settings = settings

    def get_yt_dlp_options(self) -> dict:
        """
        Возвращает словарь, который объединяется с остальными опциями yt-dlp.
        Для режима NONE словарь пустой. Ошибки конфигурации (неподдерживаемый
        браузер, отсутствующий файл, неверный формат) выбрасываются как
        исключения и обрабатываются вызывающим потоком.
        """
        if self.settings.mode == CookieMode.NONE:
            return {}
        if self.settings.mode == CookieMode.BROWSER:
            return self._get_browser_options()
        if self.settings.mode == CookieMode.FILE:
            return self._get_file_options()
        raise ValueError("Unknown cookies mode")

    def _get_browser_options(self) -> dict:
        browser = (self.settings.browser or "").lower()

        if browser not in SUPPORTED_BROWSERS:
            raise ValueError(f"Browser is not supported: {browser}")

        # Опция cookiesfrombrowser принимает кортеж
        # (браузер, профиль, keyring, контейнер). Порядок элементов важен,
        # поэтому используется кортеж, а не множество.
        if self.settings.profile:
            cookies_from_browser = (browser, self.settings.profile, None, None)
        else:
            cookies_from_browser = (browser,)

        return {"cookiesfrombrowser": cookies_from_browser}

    def _get_file_options(self) -> dict:
        if self.settings.cookie_file is None:
            raise ValueError("Cookies file is not specified")

        # expanduser раскрывает "~", resolve приводит путь к абсолютному виду.
        cookie_file = self.settings.cookie_file.expanduser().resolve()

        if not cookie_file.is_file():
            raise FileNotFoundError(f"Cookies file not found: {cookie_file}")

        self._validate_cookie_file(cookie_file)

        return {"cookiefile": str(cookie_file)}

    @staticmethod
    def _validate_cookie_file(path: Path) -> None:
        """
        Проверяет заголовок файла. yt-dlp принимает только формат Netscape,
        первая строка которого содержит фиксированный комментарий. Проверка
        позволяет сразу обнаружить выбор неподходящего файла. Кодировка
        utf-8-sig отбрасывает BOM, который добавляют некоторые расширения браузеров.
        """
        with path.open("r", encoding="utf-8-sig", errors="replace") as file:
            first_line = file.readline().strip()

        if not first_line.startswith(
            ("# Netscape HTTP Cookie File", "# HTTP Cookie File")
        ):
            raise ValueError("The file must be in Netscape cookies.txt format")
