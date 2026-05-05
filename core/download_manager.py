import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

class VideoDownloader:
    def __init__(self, opts):
        self.opts = opts

    def download(self, url):
        try:
            with yt_dlp.YoutubeDL(self.opts) as ydl:
                ydl.download(url)
        except DownloadError as e:
            print(f"Download failed: {e}")
        except ExtractorError as e:
            print(f"Extraction failed: {e}")