from scrapy import signals
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred

from scrapypuppeteer import CloseContextRequest
from scrapypuppeteer.browser_managers import BrowserManager
from scrapypuppeteer.browser_managers.playwright_browser_manager import (
    PlaywrightBrowserManager,
)
from scrapypuppeteer.browser_managers.service_browser_manager import (
    ServiceBrowserManager,
)
from scrapypuppeteer.request import ActionRequest


class BrowserDownloaderHandler(HTTPDownloadHandler):
    """
    Browser downloader handler.
    If instantiated, executes actions in the browser with provided requests.
    If given, then installed reactor must be `AsyncioSelectorReactor`.

    Currently, supports 3 browser types via EXECUTION_METHOD setting:
    * puppeteer -- see scrapy-puppeteer-service
    * pyppeteer -- not available, since the package is not actively supported
    * playwright -- see https://playwright.dev/python/
    """

    EXECUTION_METHOD_SETTING = "EXECUTION_METHOD"

    def __init__(self, settings, browser_manager: BrowserManager, crawler=None) -> None:
        super().__init__(settings, crawler=crawler)
        verify_installed_reactor(
            "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
        )

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
                raise ValueError("Currently, pyppeteer cannot run on some machines since it is not actively supported.")
            case "playwright":
                browser_manager = PlaywrightBrowserManager()
            case _:
                raise ValueError(
                    f"Invalid execution method: {execution_method.upper()}"
                )

        bdh = cls(settings, browser_manager, crawler=crawler)
        crawler.signals.connect(
            bdh.browser_manager.start_browser_manager, signals.spider_opened
        )  # This makes the start VERY slow
        crawler.signals.connect(
            bdh.browser_manager.stop_browser_manager, signals.engine_stopped
        )
        return bdh

    def download_request(self, request, spider):
        if isinstance(request, (ActionRequest, CloseContextRequest)):
            dfd_or_request = self.browser_manager.download_request(request, spider)
            if isinstance(dfd_or_request, Deferred):
                return dfd_or_request
        return super().download_request(request, spider)
