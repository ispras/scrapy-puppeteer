from urllib.parse import urlencode
from scrapy import Spider, Request
from scrapy.linkextractors import LinkExtractor

import time


class MockServerSpider(Spider):
    def __init__(self, mockserver=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mockserver = mockserver


class MetaSpider(MockServerSpider):
    name = "meta"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.meta = {}

    def closed(self, reason):
        self.meta["close_reason"] = reason


class FollowAllSpider(MetaSpider):
    name = "follow"
    link_extractor = LinkExtractor()

    def __init__(
        self, total=10, show=20, order="rand", maxlatency=0.0, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.urls_visited = []
        self.times = []
        qargs = {"total": total, "show": show, "order": order, "maxlatency": maxlatency}
        url = self.mockserver.url(f"/follow?{urlencode(qargs, doseq=True)}")
        print(f"READY URL: {url}")
        self.start_urls = [url]

    def parse(self, response, **kwargs):
        self.urls_visited.append(response.url)
        self.times.append(time.time())
        for link in self.link_extractor.extract_links(response):
            yield Request(link.url, callback=self.parse)
