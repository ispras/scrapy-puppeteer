from scrapy import Spider
from scrapy.http import Response

from scrapypuppeteer import GoTo, PuppeteerRequest, PuppeteerResponse


class FollowSpider(Spider):
    name = "follow"

    start_urls = ["http://quotes.toscrape.com/page/1/"]

    def start_requests(self):
        for url in self.start_urls:
            yield PuppeteerRequest(
                GoTo(url),
                close_page=False,
                callback=self.goto_about,
                errback=self.errback,
            )

    def goto_about(self, response: PuppeteerResponse):
        # yield response.follow(
        #     response.css("div.quote span a")[0],
        #     callback=self.parse,
        #     errback=self.errback,
        #     close_page=False,
        # )

        # Or:
        yield from response.follow_all(
            response.css("div.quote span a"),
            callback=self.parse,
            errback=self.errback,
            close_page=True,
        )

        # Or:
        # yield from response.follow_all(
        #     css="div.quote span a",
        #     callback=self.parse,
        #     errback=self.errback,
        #     close_page=False,
        # )

    def parse(self, response: Response, **kwargs):
        self.log(response.url.split("/")[-1])

    def errback(self, failure):
        self.log(failure)
