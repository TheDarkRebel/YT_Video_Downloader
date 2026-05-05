from core import download_manager as dm

def main():
    ydl_opts = {
        'format' : 'best',  # Формат видео
        'outtmpl': '%(title)s.%(ext)s',     # Шаблоны названия для вывода
        'noplaylist': True,         # Без плейлиста

        'js_runtime': {'deno': {}},

        'cookiesfrombrowser' : ('chrome',),     # Браузер для куки

        'nocheckcertificate' : True,
        'geo_pass' : True,
        'verbose' : True,
    }
    downloader = dm.VideoDownloader(ydl_opts)
    downloader.download('https://www.youtube.com/watch?v=bFjxL1rwwoE')

if __name__ == "__main__":
    main()