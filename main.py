# Точка входа в приложение.
# Модуль создает QApplication и главное окно; вся остальная логика находится
# в пакетах gui (интерфейс) и core (загрузка, настройки, cookies, обновление).
import sys

from PySide6.QtWidgets import QApplication

from gui.gui import MainWindow


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # app.exec() запускает цикл обработки событий Qt и блокируется до закрытия
    # последнего окна. Возвращенный код выхода передается в sys.exit, чтобы
    # процесс завершился с корректным статусом.
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
