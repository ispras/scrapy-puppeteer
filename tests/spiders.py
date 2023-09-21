from typing import Iterable
from urllib.parse import urlencode
from scrapy import Spider, Request
from scrapy.linkextractors import LinkExtractor
from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import GoTo, Click, Screenshot

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
        self.start_urls = [url]

    def parse(self, response, **kwargs):
        self.urls_visited.append(response.url)
        self.times.append(time.time())
        for link in self.link_extractor.extract_links(response):
            yield Request(link.url, callback=self.parse)


class GoToSpider(MetaSpider):
    name = "goto"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls_visited = []

    def start_requests(self) -> Iterable[Request]:
        yield PuppeteerRequest(GoTo("https://some_url.com"),
                               callback=self.parse, errback=self.errback,
                               close_page=False)

    def parse(self, response, **kwargs):
        body = b'''
            <html> <head></head> <body></body>
        '''
        if response.body == body:
            self.urls_visited.append(response.url)

    def errback(self, failure):
        print(failure)


class ClickSpider(MetaSpider):
    name = "click"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls_visited = []

    def start_requests(self) -> Iterable[Request]:
        yield PuppeteerRequest(GoTo("https://some_url.com"),
                               callback=self.click, errback=self.errback,
                               close_page=False)

    def click(self, response, **kwargs):
        yield response.follow(Click("the_selector"),
                              callback=self.parse, errback=self.errback,
                              close_page=False)

    def parse(self, response, **kwargs):
        body = b'''
            <html> <head></head> <body>clicked</body>
        '''
        if response.body == body:
            self.urls_visited.append(response.url)

    def errback(self, failure):
        print(failure)


class ScreenshotSpider(MetaSpider):
    name = "screenshot"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls_visited = []

    def start_requests(self) -> Iterable[Request]:
        yield PuppeteerRequest(GoTo("https://some_url.com"),
                               callback=self.screenshot, errback=self.errback,
                               close_page=False)

    def screenshot(self, response, **kwargs):
        yield response.follow(Screenshot(),
                              callback=self.parse, errback=self.errback,
                              close_page=False)

    def parse(self, response, **kwargs):
        from base64 import b64encode
        with open("./tests/scrapy_logo.png", 'rb') as image:
            if b64encode(image.read()) == response.screenshot:
                self.urls_visited.append(response.url)

    def errback(self, failure):
        print(failure)
