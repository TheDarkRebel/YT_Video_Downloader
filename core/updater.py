# Обновление yt-dlp из приложения.
# YouTube регулярно меняет защиту, и устаревшая версия yt-dlp перестает
# работать (ошибки извлечения, HTTP 403, запрос подтверждения "я не бот").
# Модуль устанавливает последнюю версию пакета через pip в отдельном потоке.
import subprocess
import sys

from PySide6.QtCore import QThread, Signal

from utils.logger import get_logger

log = get_logger()


def _installed_version() -> str:
    """
    Возвращает версию yt-dlp, установленную на диске.

    Версия читается отдельным процессом: модуль yt_dlp в работающей программе
    уже загружен в память и возвращал бы прежний номер даже после обновления,
    а новый процесс импортирует актуальные файлы.
    """
    result = subprocess.run(
        [sys.executable, "-c",
         "from yt_dlp.version import __version__ as v; print(v)"],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip() or "?"


class YtDlpUpdater(QThread):
    """
    Поток обновления yt-dlp.

    finished_signal - старая и новая версия (строки); совпадение означает,
                      что установлена последняя версия
    error_signal    - текст ошибки
    """
    finished_signal = Signal(str, str)
    error_signal = Signal(str)

    def run(self):
        try:
            # В приложении, собранном через PyInstaller или py2app, pip
            # недоступен, поэтому обновление в таком режиме не поддерживается.
            if getattr(sys, "frozen", False):
                raise RuntimeError(
                    "Updating via pip is not available in a packaged application."
                )

            old = _installed_version()
            log.info("Updating yt-dlp, current version: %s", old)

            # pip запускается тем же интерпретатором, под которым работает
            # программа, чтобы обновился именно используемый экземпляр yt-dlp.
            # Таймаут ограничивает ожидание при проблемах с сетью.
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U",
                 "--disable-pip-version-check", "yt-dlp"],
                capture_output=True, text=True, timeout=300,
            )
            log.info(result.stdout)

            if result.returncode != 0:
                # В окно передается только конец вывода (последние 500 символов),
                # полный текст сохраняется в логе.
                raise RuntimeError(
                    (result.stderr or result.stdout).strip()[-500:]
                )

            new = _installed_version()
            log.info("yt-dlp version after update: %s", new)
            self.finished_signal.emit(old, new)

        except Exception as e:
            log.exception("Failed to update yt-dlp")
            self.error_signal.emit(str(e))
