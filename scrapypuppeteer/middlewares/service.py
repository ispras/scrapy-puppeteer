import logging
from collections import defaultdict
from typing import List, Union

from scrapy import signals
from scrapy.crawler import Crawler

from scrapypuppeteer.browser_managers import BrowserManager
from scrapypuppeteer.browser_managers.playwright_browser_manager import (
    PlaywrightBrowserManager,
)
from scrapypuppeteer.browser_managers.pyppeteer_browser_manager import (
    PyppeteerBrowserManager,
)
from scrapypuppeteer.browser_managers.service_browser_manager import (
    ServiceBrowserManager,
)


class PuppeteerServiceDownloaderMiddleware:
    """
    This downloader middleware converts PuppeteerRequest instances to
    Puppeteer service API requests and then converts its responses to
    PuppeteerResponse instances. Additionally, it tracks all browser contexts
    that spider uses and performs cleanup request to service right before
    spider is closed.

        Additionally, the middleware uses these meta-keys, do not use them, because their changing
    could possibly (almost probably) break determined behaviour:
    'puppeteer_request', 'dont_obey_robotstxt', 'proxy'

    Settings:

    PUPPETEER_SERVICE_URL (str)
    Service URL, e.g. 'http://localhost:3000'

    PUPPETEER_INCLUDE_HEADERS (bool|list[str])
    Determines which request headers will be sent to remote site by puppeteer service.
    Either True (all headers), False (no headers) or list of header names.
    May be overridden per request.
    By default, only cookies are sent.

    PUPPETEER_INCLUDE_META (bool)
    Determines whether to send or not user's meta attached by user.
    Default to False.
    """

    SERVICE_URL_SETTING = "PUPPETEER_SERVICE_URL"
    INCLUDE_HEADERS_SETTING = "PUPPETEER_INCLUDE_HEADERS"
    SERVICE_META_SETTING = "PUPPETEER_INCLUDE_META"
    DEFAULT_INCLUDE_HEADERS = ["Cookie"]  # TODO send them separately

    EXECUTION_METHOD_SETTING = "EXECUTION_METHOD"

    service_logger = logging.getLogger(__name__)

    def __init__(
        self,
        crawler: Crawler,
        service_url: str,
        include_headers: Union[bool, List[str]],
        include_meta: bool,
        browser_manager: BrowserManager,
    ):
        self.service_base_url = service_url
        self.include_headers = include_headers
        self.include_meta = include_meta
        self.crawler = crawler
        self.used_contexts = defaultdict(set)
        self.browser_manager = browser_manager

    @classmethod
    def from_crawler(cls, crawler):
        service_url = crawler.settings.get(cls.SERVICE_URL_SETTING)
        if cls.INCLUDE_HEADERS_SETTING in crawler.settings:
            try:
                include_headers = crawler.settings.getbool(cls.INCLUDE_HEADERS_SETTING)
            except ValueError:
                include_headers = crawler.settings.getlist(cls.INCLUDE_HEADERS_SETTING)
        else:
            include_headers = cls.DEFAULT_INCLUDE_HEADERS
        include_meta = crawler.settings.getbool(cls.SERVICE_META_SETTING, False)

        execution_method = crawler.settings.get(
            cls.EXECUTION_METHOD_SETTING, "PUPPETEER"
        ).lower()

        if execution_method == "pyppeteer":
            browser_manager = PyppeteerBrowserManager()
        elif execution_method == "puppeteer":
            browser_manager = ServiceBrowserManager(
                service_url, include_meta, include_headers, crawler
            )
        elif execution_method == "playwright":
            browser_manager = PlaywrightBrowserManager()
        else:
            raise NameError("Wrong EXECUTION_METHOD")

        middleware = cls(
            crawler, service_url, include_headers, include_meta, browser_manager
        )
        crawler.signals.connect(
            middleware.browser_manager.close_used_contexts, signal=signals.spider_idle
        )
        return middleware

    def process_request(self, request, spider):
        return self.browser_manager.process_request(request)

    def process_response(self, request, response, spider):
        return self.browser_manager.process_response(self, request, response, spider)
