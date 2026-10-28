# Определение доступных разрешений видео.
# Запрос информации о видео занимает от нескольких секунд и зависит от сети,
# поэтому выполняется в отдельном потоке, чтобы интерфейс оставался отзывчивым.
import yt_dlp
from PySide6.QtCore import QThread, Signal

from core.cookie_manager import CookieManager
from utils.logger import get_logger

log = get_logger()


class FormatDetector(QThread):
    """
    Поток получения списка разрешений для указанной ссылки.

    Результат передается окну через сигналы: виджеты нельзя изменять из
    стороннего потока, а сигналы Qt безопасно доставляются в поток интерфейса.

    result_signal - название видео и список высот по убыванию, например [2160, 1080, 720]
    error_signal  - текст ошибки
    """
    result_signal = Signal(str, list)
    error_signal = Signal(str)

    def __init__(self, url, cookie_settings=None):
        super().__init__()
        self.url = url
        self.cookie_settings = cookie_settings

    def run(self):
        try:
            # Выполняется только извлечение метаданных: skip_download и
            # download=False исключают скачивание файла. noplaylist ограничивает
            # запрос одним видео, даже если ссылка содержит параметр плейлиста.
            opts = {
                "quiet": True,
                "noplaylist": True,
                "skip_download": True,
                "socket_timeout": 15,
                "retries": 3,
                "extractor_retries": 2,
            }
            # Cookies применяются и здесь: для видео с ограничениями запрос
            # без авторизации завершается ошибкой.
            if self.cookie_settings:
                opts.update(CookieManager(self.cookie_settings).get_yt_dlp_options())

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            # Из списка форматов отбираются уникальные значения высоты. Форматы
            # без видеодорожки (vcodec равен "none") и без указанной высоты
            # пропускаются.
            heights = sorted(
                {
                    f["height"]
                    for f in info.get("formats", [])
                    if f.get("height") and f.get("vcodec") != "none"
                },
                reverse=True,
            )
            log.info("Available resolutions: %s", heights)
            self.result_signal.emit(info.get("title", ""), heights)

        except Exception as e:
            log.exception("Failed to get the format list")
            self.error_signal.emit(str(e))
