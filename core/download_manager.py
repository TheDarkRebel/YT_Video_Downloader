# Загрузка видео и аудио.
# Загрузка выполняется в потоке QThread, чтобы окно оставалось отзывчивым.
# Поток взаимодействует с интерфейсом только через сигналы Qt.
import yt_dlp
from PySide6.QtCore import QThread, Signal
from yt_dlp import DownloadCancelled

from core.cookie_manager import CookieManager
from core.settings_manager import Settings
from utils.logger import get_logger

log = get_logger()


class _CancelLogger:
    """
    Логгер для yt-dlp (передается в опцию logger).

    Выполняет две задачи:
    1. Записывает сообщения yt-dlp в файл лога. Подключение собственного логгера
       отключает вывод yt-dlp в консоль.
    2. Проверяет флаг отмены при каждом сообщении. Хук прогресса вызывается
       только во время скачивания файла, а логгер срабатывает и на этапах
       получения информации о видео и повторных попыток, поэтому отмена
       действует на всех стадиях.
    """

    def __init__(self, is_cancelled):
        # Принимается функция, а не значение: флаг изменяется во время работы,
        # и при каждой проверке нужно читать его актуальное состояние.
        self._is_cancelled = is_cancelled

    def _check(self):
        # DownloadCancelled штатно прерывает работу yt-dlp.
        if self._is_cancelled():
            raise DownloadCancelled("Cancelled by user")

    def debug(self, msg):
        # Строки вида "[download] 12.3% of ..." приходят несколько раз в секунду.
        # В лог они не записываются, чтобы файл не разрастался, но флаг
        # отмены проверяется для каждой из них.
        if not (msg.startswith("[download]") and "% of" in msg):
            log.debug(msg)
        self._check()

    def info(self, msg):
        log.info(msg)
        self._check()

    def warning(self, msg):
        log.warning(msg)
        self._check()

    def error(self, msg):
        # Отмена не проверяется: ошибка должна быть записана в любом случае.
        log.error(msg)


class VideoDownloader(QThread):
    """
    Поток загрузки одного видео.

    Сигналы:
    progress_signal  - процент выполнения и текст статуса (скорость, остаток времени)
    finished_signal  - сообщение об успешном завершении
    error_signal     - текст ошибки
    cancelled_signal - загрузка отменена пользователем
    """
    progress_signal = Signal(float, str)
    finished_signal = Signal(str)
    error_signal = Signal(str)
    cancelled_signal = Signal()

    def __init__(self, url, format_type, download_dir=None,
                 max_height=None, cookie_settings=None):
        super().__init__()
        self.url = url
        self.format_type = format_type
        self.download_dir = download_dir
        self.max_height = max_height
        self.cookie_settings = cookie_settings
        # Флаг отмены выставляется из потока интерфейса методом cancel()
        # и читается внутри потока загрузки (хук прогресса и _CancelLogger).
        self._is_cancelled = False

    def cancel(self):
        """
        Запрашивает отмену загрузки. Поток не прерывается принудительно:
        он завершается при следующей проверке флага, то есть при ближайшем
        сообщении yt-dlp. Этап склейки через ffmpeg отменить нельзя.
        """
        self._is_cancelled = True

    def _progress_hook(self, d):
        """
        Хук прогресса yt-dlp. Вызывается многократно во время загрузки;
        словарь d содержит статус, число скачанных байт, общий размер
        (точный или оценочный) и готовые строки скорости и остатка времени.
        """
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            # Если размер неизвестен, процент остается нулевым.
            percent = (downloaded / total * 100) if total > 0 else 0

            speed = d.get("_speed_str", "N/A").strip()
            eta = d.get("_eta_str", "N/A").strip()
            self.progress_signal.emit(percent, f"Speed: {speed} | ETA: {eta}")
        elif d.get("status") == "finished":
            # Файл скачан; далее выполняется склейка потоков или конвертация
            # через ffmpeg, для которой хук прогресса больше не вызывается.
            self.progress_signal.emit(100, "Processing file...")

    def run(self):
        """
        Тело потока. Выполняется после вызова start(); прямой вызов run()
        запустил бы загрузку в потоке интерфейса и заблокировал окно.
        """
        log.info("-" * 60)
        log.info("Download started: %s (%s)", self.url, self.format_type)
        try:
            # Опции cookies собираются внутри потока и внутри try: ошибки
            # (файл не найден, неверный формат) попадают в error_signal
            # и отображаются в окне, а не приводят к аварийному завершению.
            cookie_opts = (
                CookieManager(self.cookie_settings).get_yt_dlp_options()
                if self.cookie_settings else {}
            )
            opts = Settings.settings(
                self._progress_hook,
                self.format_type,
                download_dir=self.download_dir,
                logger=_CancelLogger(lambda: self._is_cancelled),
                max_height=self.max_height,
                cookie_options=cookie_opts,
            )
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([self.url])

            if self._is_cancelled:
                log.info("Download cancelled")
                self.cancelled_signal.emit()
            else:
                log.info("Download finished")
                self.finished_signal.emit("Download completed successfully!")

        except DownloadCancelled:
            log.info("Download cancelled")
            self.cancelled_signal.emit()
        except Exception as e:
            # log.exception записывает в лог полный traceback.
            log.exception("Download failed")
            # Если отмена уже запрошена, ошибка, как правило, вызвана самим
            # прерыванием и сообщается как отмена.
            if self._is_cancelled:
                self.cancelled_signal.emit()
            else:
                self.error_signal.emit(str(e))
