# Сборка словаря опций для yt-dlp.
# Модуль определяет формат загрузки, папку, таймауты, подключение логгера
# и cookies. Логика выбора параметров вынесена из потока загрузки, чтобы
# изменение настроек не затрагивало код работы с потоками.

# Зарезервированный набор значений по умолчанию. В текущей версии не
# используется: рабочие значения задаются непосредственно в Settings.settings.
'''DEFAULT_SETTINGS = {
    "format": "bv*+ba/b",
    "output_template": "%(title)s.%(ext)s",
    "download_playlist": False,
    "use_browser_cookies": True,
    "browser": "chrome",
    "browser_profile": None,
    "verbose": False,
}'''


class Settings:

    @staticmethod
    def settings(progress_hook, format_type, logger=None, download_dir=None,
                 max_height=None, cookie_options=None):
        """
        Возвращает словарь опций для yt_dlp.YoutubeDL.

        progress_hook  - функция, вызываемая yt-dlp при обновлении прогресса
        format_type    - "Audio MP3" или любое другое значение (видео MP4)
        logger         - объект с методами debug/info/warning/error; передается
                         снаружи, так как зависит от флага отмены конкретного потока
        download_dir   - папка сохранения; None означает текущую рабочую директорию
        max_height     - максимальная высота видео в пикселях; None означает
                         лучшее доступное качество
        cookie_options - готовый словарь от CookieManager
        """
        # Базовые опции. socket_timeout ограничивает ожидание ответа сети
        # (секунды), retries и extractor_retries задают число повторных попыток
        # при загрузке фрагментов и при получении информации о видео.
        ydl_opts = {
            'progress_hooks': [progress_hook],
            'outtmpl': '%(title)s.%(ext)s',
            'socket_timeout': 15,
            'retries': 3,
            'extractor_retries': 2,
        }

        # Папка загрузки задается опцией paths, а не через outtmpl: шаблон
        # имени файла и расположение остаются независимыми. Недостающие
        # каталоги yt-dlp создает самостоятельно.
        if download_dir is not None:
            ydl_opts['paths'] = {'home': str(download_dir)}

        # Опции cookies уже подготовлены менеджером и добавляются без изменений.
        if cookie_options:
            ydl_opts.update(cookie_options)

        if logger is not None:
            ydl_opts['logger'] = logger

        if format_type == "Audio MP3":
            # Выбирается лучшая аудиодорожка, затем через ffmpeg
            # (постпроцессор FFmpegExtractAudio) она конвертируется в mp3
            # с битрейтом 192 kbps. Для работы нужен установленный ffmpeg.
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            # Ограничение по высоте подставляется в селектор формата.
            # Варианты перебираются слева направо до первого доступного:
            #   1. видео mp4 + аудио m4a (наиболее совместимая пара);
            #   2. любое видео + любое аудио;
            #   3. готовый файл с уже объединенными потоками.
            # Если max_height не задан, фильтр пустой и берется лучшее качество.
            # merge_output_format задает контейнер mp4 для итоговой склейки.
            h = f"[height<={max_height}]" if max_height else ""
            ydl_opts.update({
                'format': f'bv*{h}[ext=mp4]+ba[ext=m4a]/bv*{h}+ba/b{h}',
                'merge_output_format': 'mp4',
            })

        return ydl_opts
