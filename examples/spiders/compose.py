import scrapy

from scrapy.http import TextResponse
from scrapy.spidermiddlewares.httperror import HttpError
from scrapypuppeteer import PuppeteerRequest, PuppeteerResponse, PuppeteerJsonResponse
from scrapypuppeteer.actions import GoTo, Click, Screenshot, Compose
from twisted.python.failure import Failure


class DeadContextSpider(scrapy.Spider):
    name = "compose"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapypuppeteer.middleware.PuppeteerServiceDownloaderMiddleware": 1042,
        },
    }

    def start_requests(self):
        goto = GoTo("https://pptr.dev")
        click_1 = Click(
            "#__docusaurus > nav > div.navbar__inner > div:nth-child(1) > a:nth-child(3)"
        )
        click_2 = Click(
            "#__docusaurus_skipToContent_fallback > div > div > aside > div > "
            "div > nav > ul > li:nth-child(1) > ul > li:nth-child(3) > a"
        )
        click = Compose(click_1, click_2)
        screenshot = Screenshot(options={"full_page": True, "type": "jpeg"})

        compose_action = Compose(
            goto,
            click,
            screenshot,
        )

        yield PuppeteerRequest(
            compose_action,
            callback=self.parse,
            errback=self.errback,
            close_page=True,
        )

    def parse(self, response: PuppeteerResponse):
        print(response.body)
        self.log("Spider worked fine!")

    @staticmethod
    def errback(failure: Failure):
        value: HttpError = failure.value
        response: TextResponse = value.response
        puppeteer_request = response.request.meta.get("puppeteer_request")
        print(puppeteer_request.url)
