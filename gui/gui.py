# Пользовательский интерфейс: главное окно и диалог настроек.
# Модуль отвечает только за отображение и обработку действий пользователя.
# Тяжелые операции (загрузка, проверка форматов, обновление) выполняются
# в потоках из пакета core, результаты поступают через сигналы Qt.
import re
from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QDialog,
    QFileDialog,
    QFormLayout,
)

from core.cookie_manager import CookieMode, CookieSettings, SUPPORTED_BROWSERS
from core.download_manager import VideoDownloader
from core.format_detector import FormatDetector
from core.updater import YtDlpUpdater


class MainWindow(QMainWindow):
    """
    Главное окно приложения.

    Хранит пользовательские настройки (папка загрузки, параметры cookies),
    запускает потоки загрузки, проверки форматов и обновления yt-dlp
    и отображает их состояние.
    """

    def __init__(self):
        super().__init__()

        # Ссылки на потоки хранятся в атрибутах: если поток остается без ссылки,
        # сборщик мусора может удалить его во время работы. Значение None
        # означает, что поток еще не создавался.
        self.worker = None
        self.updater = None
        self.detector = None

        # Постоянные настройки сохраняются между запусками через QSettings
        # (на macOS это plist-файл в ~/Library/Preferences). Папка загрузки
        # по умолчанию: ~/Downloads/YT_Downloader.
        self.qsettings = QSettings("YTVideoDownloader", "YTVideoDownloader")
        self.download_dir = Path(
            self.qsettings.value(
                "download_dir", str(Path.home() / "Downloads" / "YT_Downloader")
            )
        )
        self.cookie_settings = self.load_cookie_settings()

        # ======== Настройки окна ========
        self.setWindowTitle("YouTube Downloader v1.0")
        self.resize(500, 300)

        # ======== Главный виджет ========
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        # ======== Основной layout (вертикальная компоновка блоков) ========
        self.main_layout = QVBoxLayout()

        # ======== Заголовок ========
        self.title = QLabel("YouTube Downloader")
        self.title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.main_layout.addWidget(self.title)

        # ======== URL ========
        self.url_layout = QHBoxLayout()
        self.url_label = QLabel("URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube URL")
        self.url_layout.addWidget(self.url_label)
        self.url_layout.addWidget(self.url_input)
        self.main_layout.addLayout(self.url_layout)

        # ======== Формат ========
        self.format_layout = QHBoxLayout()
        self.format_label = QLabel("Format:")
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Video MP4",
            "Audio MP3"
        ])
        self.format_layout.addWidget(self.format_label)
        self.format_layout.addWidget(self.format_combo)
        self.main_layout.addLayout(self.format_layout)

        # ======== Качество ========
        # Список разрешений заполняется кнопкой Check. Значение "Best"
        # хранит None в качестве данных и означает отсутствие ограничения по высоте;
        # для остальных пунктов данными служит число (высота в пикселях).
        self.quality_layout = QHBoxLayout()
        self.quality_label = QLabel("Quality:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Best", None)
        self.check_button = QPushButton("Check")
        self.check_button.clicked.connect(self.check_formats)
        self.quality_layout.addWidget(self.quality_label)
        self.quality_layout.addWidget(self.quality_combo)
        self.quality_layout.addWidget(self.check_button)
        self.main_layout.addLayout(self.quality_layout)

        # Для аудио выбор качества видео не применяется
        self.format_combo.currentTextChanged.connect(self.on_format_changed)

        # ======== Прогресс бар и статус ========
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to work")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.main_layout.addWidget(self.status_label)

        # ======== Кнопки ========
        # Кнопка отмены неактивна, пока загрузка не запущена.
        self.button_layout = QHBoxLayout()

        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_download)

        self.update_button = QPushButton("Update yt-dlp")
        self.update_button.clicked.connect(self.update_ytdlp)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.open_settings)

        self.button_layout.addWidget(self.download_button)
        self.button_layout.addWidget(self.cancel_button)
        self.button_layout.addWidget(self.update_button)
        self.button_layout.addWidget(self.settings_button)

        # Сборка итоговой компоновки
        self.main_layout.addLayout(self.button_layout)
        self.main_widget.setLayout(self.main_layout)

    # ======================== Загрузка ========================

    def set_downloading(self, active: bool):
        """
        Переключает доступность кнопок: во время загрузки кнопка Download
        блокируется, а Cancel становится активной; после завершения наоборот.
        """
        self.download_button.setEnabled(not active)
        self.cancel_button.setEnabled(active)

    def update_progress(self, percent, status_text):
        """Слот сигнала progress_signal: обновляет прогресс-бар и строку статуса."""
        self.progress_bar.setValue(int(percent))
        self.status_label.setText(status_text)

    def start_download(self):
        """
        Проверяет введенную ссылку и запускает поток загрузки.

        Проверка выполняется в два шага: сначала строка на пустоту, затем
        по регулярному выражению, которое допускает ссылки видов youtube.com/watch?v=...,
        youtube.com/embed/..., youtu.be/... с 11-символьным идентификатором видео.
        Параметры потока (папка, ограничение высоты, cookies) берутся из текущего
        состояния окна на момент нажатия кнопки; их последующее изменение
        на уже запущенную загрузку не влияет.
        """
        url = self.url_input.text().strip()
        format_choice = self.format_combo.currentText()
        pattern = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"

        if not url:
            QMessageBox.warning(self, "Error", "Please, enter video link!")
            return

        if not re.match(pattern, url):
            QMessageBox.warning(self, "Link is incorrect.", "Please, enter video link correctly!")
            return

        self.set_downloading(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Please wait...")

        self.worker = VideoDownloader(
            url, format_choice,
            download_dir=self.download_dir,
            max_height=self.quality_combo.currentData(),
            cookie_settings=self.cookie_settings,
        )
        # Сигналы потока подключаются к методам окна; именно через них
        # поток безопасно обновляет интерфейс.
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.download_finished)
        self.worker.error_signal.connect(self.download_error)
        self.worker.cancelled_signal.connect(self.download_cancelled)
        self.worker.start()

    def cancel_download(self):
        """
        Запрашивает отмену текущей загрузки. Остановка происходит не мгновенно:
        поток проверяет флаг при следующем сообщении yt-dlp. Кнопка блокируется
        сразу, чтобы исключить повторные нажатия.
        """
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Cancelling...")

    def download_cancelled(self):
        """Слот cancelled_signal: сбрасывает прогресс и возвращает кнопки в исходное состояние."""
        self.progress_bar.setValue(0)
        self.status_label.setText("Download has been interrupted")
        self.set_downloading(False)

    def download_finished(self, message):
        """Слот finished_signal: сообщает об успешном завершении загрузки."""
        self.status_label.setText("Done!")
        self.set_downloading(False)
        QMessageBox.information(self, "Success!", message)

    def download_error(self, error_message):
        """Слот error_signal: отображает текст ошибки, полученный из потока."""
        self.status_label.setText("Something went wrong :(")
        self.set_downloading(False)
        QMessageBox.critical(self, "Error!", f"Cannot download:\n {error_message}")

    def closeEvent(self, event):
        """
        Обработчик закрытия окна (вызывается Qt автоматически). Перед выходом
        запущенные потоки останавливаются или ожидаются, чтобы процесс не
        завершился во время записи файла или установки пакета.
        Тайм-ауты ожидания: 3 с для загрузки, 10 с для обновления.
        """
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
        if self.updater and self.updater.isRunning():
            self.updater.wait(10000)
        event.accept()

    # ======================== Выбор качества ========================

    def on_format_changed(self, text):
        """Отключает выбор качества и кнопку Check для аудио: разрешение в этом режиме не используется."""
        is_video = text != "Audio MP3"
        self.quality_combo.setEnabled(is_video)
        self.check_button.setEnabled(is_video)

    def check_formats(self):
        """
        Запускает поток получения списка доступных разрешений для введенной ссылки.
        Кнопка блокируется до получения результата.
        """
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please, enter video link!")
            return

        self.check_button.setEnabled(False)
        self.status_label.setText("Fetching available formats...")

        self.detector = FormatDetector(url, self.cookie_settings)
        self.detector.result_signal.connect(self.on_formats_ready)
        self.detector.error_signal.connect(self.on_formats_error)
        self.detector.start()

    def on_formats_ready(self, title, heights):
        """
        Слот result_signal: заполняет список качества полученными разрешениями
        (первым всегда остается пункт Best) и выводит название видео в строке статуса.
        """
        self.quality_combo.clear()
        self.quality_combo.addItem("Best", None)
        for h in heights:
            self.quality_combo.addItem(f"{h}p", h)

        self.check_button.setEnabled(True)
        self.status_label.setText(title or "Ready to work")

    def on_formats_error(self, message):
        """Слот error_signal потока проверки форматов."""
        self.check_button.setEnabled(True)
        self.status_label.setText("Could not fetch formats")
        QMessageBox.critical(self, "Error!", f"Cannot check formats:\n {message}")

    # ======================== Настройки ========================

    def load_cookie_settings(self) -> CookieSettings:
        """
        Читает параметры cookies из QSettings. При неизвестном или поврежденном
        значении режима используется CookieMode.NONE. Пустые строки
        преобразуются в None.
        """
        q = self.qsettings
        try:
            mode = CookieMode(q.value("cookie_mode", CookieMode.NONE.value))
        except ValueError:
            mode = CookieMode.NONE

        cookie_file = q.value("cookie_file", "")
        return CookieSettings(
            mode=mode,
            browser=q.value("cookie_browser", "chrome"),
            profile=q.value("cookie_profile", "") or None,
            cookie_file=Path(cookie_file) if cookie_file else None,
        )

    def save_cookie_settings(self, cs: CookieSettings):
        """Записывает параметры cookies в QSettings (None сохраняется как пустая строка)."""
        q = self.qsettings
        q.setValue("cookie_mode", cs.mode.value)
        q.setValue("cookie_browser", cs.browser or "")
        q.setValue("cookie_profile", cs.profile or "")
        q.setValue("cookie_file", str(cs.cookie_file) if cs.cookie_file else "")

    def open_settings(self):
        """
        Открывает модальный диалог настроек. Диалог получает текущие значения
        и не изменяет состояние окна сам: новые значения применяются и сохраняются
        только при подтверждении (кнопка Save), при отмене остаются прежние.
        """
        dialog = SettingsWindow(self.download_dir, self.cookie_settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.download_dir = dialog.get_download_dir()
            self.cookie_settings = dialog.get_cookie_settings()
            self.qsettings.setValue("download_dir", str(self.download_dir))
            self.save_cookie_settings(self.cookie_settings)

    # ======================== Обновление yt-dlp ========================

    def update_ytdlp(self):
        """
        Запускает поток обновления yt-dlp. Во время загрузки обновление
        недоступно: замена файлов библиотеки при активной работе может
        привести к сбою. На время обновления блокируются кнопки Update и Download.
        """
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self, "Update", "Wait for the download to finish or cancel it first."
            )
            return

        self.update_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.status_label.setText("Updating yt-dlp...")

        self.updater = YtDlpUpdater()
        self.updater.finished_signal.connect(self.on_update_finished)
        self.updater.error_signal.connect(self.on_update_error)
        self.updater.start()

    def on_update_finished(self, old, new):
        """
        Слот finished_signal потока обновления. Если версия не изменилась,
        сообщается об актуальной версии. После успешного обновления требуется
        перезапуск, так как модуль yt_dlp уже загружен в память процесса.
        """
        self.update_button.setEnabled(True)
        self.download_button.setEnabled(True)
        self.status_label.setText("Ready to work")

        if old == new:
            QMessageBox.information(
                self, "Update", f"The latest version is already installed ({new})."
            )
        else:
            QMessageBox.information(
                self, "Update",
                f"yt-dlp updated: {old} -> {new}\n\n"
                "Restart the application to apply the changes.",
            )

    def on_update_error(self, message):
        """Слот error_signal потока обновления."""
        self.update_button.setEnabled(True)
        self.download_button.setEnabled(True)
        self.status_label.setText("Could not update yt-dlp")
        QMessageBox.critical(self, "Error!", f"Cannot update:\n {message}")


class SettingsWindow(QDialog):
    """
    Модальный диалог настроек: папка загрузки и параметры cookies.

    Диалог не знает о главном окне. Он принимает текущие значения в конструкторе
    и возвращает новые через get_download_dir() и get_cookie_settings();
    применение и сохранение выполняет вызывающая сторона.
    """

    # Пары (подпись в списке, режим). Порядок элементов определяет порядок в списке.
    MODES = [
        ("No cookies", CookieMode.NONE),
        ("From browser", CookieMode.BROWSER),
        ("From cookies.txt file", CookieMode.FILE),
    ]

    def __init__(self, download_dir, cookie_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(450, 250)

        layout = QVBoxLayout()
        form = QFormLayout()

        # --- Папка загрузки ---
        self.dir_input = QLineEdit(str(download_dir))
        dir_browse = QPushButton("Browse...")
        dir_browse.clicked.connect(self.browse_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.dir_input)
        dir_row.addWidget(dir_browse)
        form.addRow("Download folder:", dir_row)

        # --- Cookies ---
        # Режим хранится в данных элемента списка (currentData), поэтому
        # преобразование из текста в CookieMode не требуется.
        self.mode_combo = QComboBox()
        for title, mode in self.MODES:
            self.mode_combo.addItem(title, mode)
        self.mode_combo.setCurrentIndex(
            [m for _, m in self.MODES].index(cookie_settings.mode)
        )
        self.mode_combo.currentIndexChanged.connect(self.update_cookie_fields)
        form.addRow("Cookies:", self.mode_combo)

        self.browser_combo = QComboBox()
        self.browser_combo.addItems(sorted(SUPPORTED_BROWSERS))
        if cookie_settings.browser:
            self.browser_combo.setCurrentText(cookie_settings.browser)
        form.addRow("Browser:", self.browser_combo)

        self.file_input = QLineEdit(
            str(cookie_settings.cookie_file) if cookie_settings.cookie_file else ""
        )
        file_browse = QPushButton("Browse...")
        file_browse.clicked.connect(self.browse_file)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_input)
        file_row.addWidget(file_browse)
        form.addRow("File:", file_row)

        layout.addLayout(form)

        # --- Кнопки ---
        # accept и reject закрывают диалог с результатом Accepted и Rejected.
        buttons = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        self.setLayout(layout)
        self.update_cookie_fields()

    def update_cookie_fields(self):
        """Включает только те поля, которые относятся к выбранному режиму cookies."""
        mode = self.mode_combo.currentData()
        self.browser_combo.setEnabled(mode == CookieMode.BROWSER)
        self.file_input.setEnabled(mode == CookieMode.FILE)

    def browse_dir(self):
        """Открывает системный диалог выбора папки, начиная с текущего значения поля."""
        chosen = QFileDialog.getExistingDirectory(
            self, "Select folder", self.dir_input.text()
        )
        if chosen:
            self.dir_input.setText(chosen)

    def browse_file(self):
        """Открывает системный диалог выбора файла cookies."""
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Cookies file", "", "Text files (*.txt);;All files (*)"
        )
        if chosen:
            self.file_input.setText(chosen)

    def get_download_dir(self) -> Path:
        """Возвращает выбранную папку загрузки (символ "~" раскрывается)."""
        return Path(self.dir_input.text().strip()).expanduser()

    def get_cookie_settings(self) -> CookieSettings:
        """
        Собирает CookieSettings из полей диалога. Профиль браузера в интерфейсе
        не настраивается, поэтому всегда равен None (используется профиль
        по умолчанию).
        """
        file_text = self.file_input.text().strip()
        return CookieSettings(
            mode=self.mode_combo.currentData(),
            browser=self.browser_combo.currentText(),
            profile=None,
            cookie_file=Path(file_text) if file_text else None,
        )
