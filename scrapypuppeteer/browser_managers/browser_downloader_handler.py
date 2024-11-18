from collections.abc import Coroutine

from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured
from scrapy.utils.defer import deferred_from_coro
from scrapy.utils.reactor import verify_installed_reactor

from scrapypuppeteer import CloseContextRequest
from scrapypuppeteer.browser_managers import BrowserManager
from scrapypuppeteer.browser_managers.playwright_browser_manager import PlaywrightBrowserManager
from scrapypuppeteer.browser_managers.pyppeteer_browser_manager import PyppeteerBrowserManager
from scrapypuppeteer.browser_managers.service_browser_manager import ServiceBrowserManager
from scrapypuppeteer.request import ActionRequest


class BrowserDownloaderHandler(HTTPDownloadHandler):
    """
        docstring: TODO
    """

    EXECUTION_METHOD_SETTING = "EXECUTION_METHOD"

    def __init__(self, settings, browser_manager: BrowserManager, crawler=None) -> None:
        super().__init__(settings, crawler=crawler)
        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")

        self.browser_manager = browser_manager

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        settings = crawler.settings

        execution_method = crawler.settings.get(
            cls.EXECUTION_METHOD_SETTING, "PUPPETEER"
        ).lower()

        match execution_method:
            case "puppeteer":
                browser_manager = ServiceBrowserManager()
            case "pyppeteer":
                browser_manager = PyppeteerBrowserManager()
            case "playwright":
                browser_manager = PlaywrightBrowserManager()
            case _:
                raise ValueError(f"Invalid execution method: {execution_method.upper()}")

        return cls(settings, browser_manager, crawler=crawler)

    def download_request(self, request, spider):
        if isinstance(request, (ActionRequest, CloseContextRequest)):
            coro_or_request = self.browser_manager.download_request(request, spider)
            if isinstance(coro_or_request, Coroutine):
                return deferred_from_coro(coro_or_request)
        return super().download_request(request, spider)
