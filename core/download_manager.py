import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError
from core import cookie_manager as cm


class VideoDownloader:
    def __init__(self, opts: dict, cookie_manager: cm.CookieManager | None = None):
        self.base_opts = opts
        self.cookie_manager = cookie_manager

    def _build_options(self) -> dict:
        options = self.base_opts.copy()

        if self.cookie_manager is not None:
            cookie_options = (self.cookie_manager.get_yt_dlp_options())
            options.update(cookie_options)

        return options


    def download(self, url) -> None:
        options = self._build_options()

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download(url)
        except DownloadError as e:
            raise DownloadError(f"Download failed: {e}")
        except ExtractorError as e:
            raise ExtractorError(f"Extraction failed: {e}")