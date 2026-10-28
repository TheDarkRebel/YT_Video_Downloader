# Настройка логирования.
# Все сообщения приложения и библиотеки yt-dlp записываются в один файл,
# по которому можно восстановить ход работы и причины ошибок.
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Лог хранится в домашней папке пользователя, поэтому его расположение
# не зависит от рабочей директории и способа запуска (IDE, терминал, сборка).
LOG_DIR = Path.home() / ".yt_video_downloader" / "logs"
LOG_FILE = LOG_DIR / "app.log"


def get_logger(name: str = "ytdl") -> logging.Logger:
    """
    Возвращает настроенный логгер с записью в файл.

    Функция безопасна для повторных вызовов: logging.getLogger возвращает один
    и тот же объект для одного имени, а обработчик добавляется только при первом
    вызове. Без этой проверки каждое сообщение дублировалось бы по числу вызовов.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # RotatingFileHandler ограничивает размер лога: при достижении maxBytes
    # текущий файл переименовывается в app.log.1 (предыдущие сдвигаются дальше),
    # а запись продолжается в новый app.log. Хранится не более backupCount
    # архивных файлов, самые старые удаляются.
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    # Заголовок записывается один раз за запуск и визуально отделяет сеансы
    # друг от друга в общем файле.
    logger.info("=" * 60)
    logger.info("Application started")
    logger.info("=" * 60)

    return logger
