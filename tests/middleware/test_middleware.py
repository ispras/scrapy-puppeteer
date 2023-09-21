from tests.spiders import FollowAllSpider, GoToSpider, ClickSpider, ScreenshotSpider
from tests.mockserver import MockServer
from twisted.trial.unittest import TestCase
from twisted.internet import defer
from scrapy.utils.test import get_crawler


class CrawlTestCase(TestCase):
    SETTINGS = {
        'DOWNLOADER_MIDDLEWARES': {
            'scrapypuppeteer.middleware.PuppeteerServiceDownloaderMiddleware': 1042
        },
        'PUPPETEER_SERVICE_URL': None,
    }

    def setUp(self):
        self.mockserver = MockServer()
        self.mockserver.__enter__()
        self.SETTINGS['PUPPETEER_SERVICE_URL'] = self.mockserver.http_address

    def tearDown(self):
        self.mockserver.__exit__(None, None, None)

    @defer.inlineCallbacks
    def test_follow_all(self):
        crawler = get_crawler(FollowAllSpider)
        yield crawler.crawl(mockserver=self.mockserver)
        self.assertEqual(len(crawler.spider.urls_visited), 11)  # 10 + start_url

    @defer.inlineCallbacks
    def test_goto(self):
        crawler = get_crawler(GoToSpider, self.SETTINGS)
        yield crawler.crawl(mockserver=self.mockserver)
        self.assertEqual(len(crawler.spider.urls_visited), 1)

    @defer.inlineCallbacks
    def test_click(self):
        crawler = get_crawler(ClickSpider, self.SETTINGS)
        yield crawler.crawl(mockserver=self.mockserver)
        self.assertEqual(len(crawler.spider.urls_visited), 1)

    @defer.inlineCallbacks
    def test_screenshot(self):
        crawler = get_crawler(ScreenshotSpider, self.SETTINGS)
        yield crawler.crawl(mockserver=self.mockserver)
        self.assertEqual(len(crawler.spider.urls_visited), 1)
