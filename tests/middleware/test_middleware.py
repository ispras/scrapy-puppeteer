from scrapy.utils.test import get_crawler
from twisted.internet import defer
from twisted.trial.unittest import TestCase

from tests.mockserver import MockServer
from tests.spiders import (
    ClickSpider,
    CustomJsActionSpider,
    GoBackForwardSpider,
    GoToSpider,
    RecaptchaSolverSpider,
    ScreenshotSpider,
)


class PuppeteerCrawlTest(TestCase):
    SETTINGS = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapypuppeteer.middleware.PuppeteerServiceDownloaderMiddleware": 1042
        },
        "PUPPETEER_SERVICE_URL": None,
    }

    def setUp(self):
        self.mockserver = MockServer()
        self.mockserver.__enter__()
        self.SETTINGS["PUPPETEER_SERVICE_URL"] = self.mockserver.http_address

    def tearDown(self):
        self.mockserver.__exit__(None, None, None)

    def _start_testing(self, spider_cls, expected):
        crawler = get_crawler(spider_cls, self.SETTINGS)
        yield crawler.crawl(mockserver=self.mockserver)
        self.assertEqual(expected, len(crawler.spider.urls_visited))

    @defer.inlineCallbacks
    def test_goto(self):
        yield from self._start_testing(GoToSpider, 1)

    @defer.inlineCallbacks
    def test_back_forward(self):
        yield from self._start_testing(GoBackForwardSpider, 1)

    @defer.inlineCallbacks
    def test_click(self):
        yield from self._start_testing(ClickSpider, 1)

    @defer.inlineCallbacks
    def test_screenshot(self):
        yield from self._start_testing(ScreenshotSpider, 1)

    @defer.inlineCallbacks
    def test_custom_js_action(self):
        yield from self._start_testing(CustomJsActionSpider, 1)

    @defer.inlineCallbacks
    def test_recaptcha_solver(self):
        yield from self._start_testing(RecaptchaSolverSpider, 1)
