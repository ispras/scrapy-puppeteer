from tests.spiders import FollowAllSpider
from tests.mockserver import MockServer
from twisted.trial.unittest import TestCase
from twisted.internet import defer
from scrapy.utils.test import get_crawler


class CrawlTestCase(TestCase):
    def setUp(self):
        self.mockserver = MockServer()
        self.mockserver.__enter__()

    def tearDown(self):
        self.mockserver.__exit__(None, None, None)

    @defer.inlineCallbacks
    def test_follow_all(self):
        crawler = get_crawler(FollowAllSpider)
        yield crawler.crawl(mockserver=self.mockserver)
        self.assertEqual(len(crawler.spider.urls_visited), 11)  # 10 + start_url
