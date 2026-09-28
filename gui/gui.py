import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QLineEdit,
)

from tests.dm_test import downloader

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # ======== Настройки окна ========

        self.setWindowTitle("YouTube Downloader v1.0")
        self.resize(500, 300)

        # ======== Главный виджет ========

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        # ======== Основной layout ========

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

        # ======== Кнопки ========

        self.button_layout = QHBoxLayout()

        self.download_button = QPushButton("Download")
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(GuiHandler.open_settings)

        self.button_layout.addWidget(self.download_button)
        self.button_layout.addWidget(self.settings_button)

        # ======== Добавление layout'ов ========

        self.main_layout.addLayout(self.url_layout)
        self.main_layout.addLayout(self.format_layout)
        self.main_layout.addLayout(self.button_layout)

        self.main_widget.setLayout(self.main_layout)



class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ======= Настройка окна =======
        self.setWindowTitle("Settings")
        self.resize(300, 300)

        # ======= Главный виджет ========
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        self.button_layout = QHBoxLayout()
        self.but = QPushButton("Close")
        self.button_layout.addWidget(self.but)

        self.main_widget.setLayout(self.button_layout)


class GuiHandler:

    @staticmethod
    def download_on_click(self):
        link = MainWindow.url_input.text()

        if not link:
            print("link is empty!")
            return

        downloader.download(link)

    @staticmethod
    def open_settings():
        window = SettingsWindow()
        window.show()