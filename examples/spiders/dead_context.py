from asyncio import sleep

import scrapy
from twisted.python.failure import Failure

from scrapypuppeteer import PuppeteerRequest, PuppeteerResponse
from scrapypuppeteer.actions import Click, GoTo


class DeadContextSpider(scrapy.Spider):
    custom_settings = {
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOADER_MIDDLEWARES": {
            "scrapypuppeteer.middleware.PuppeteerContextRestoreDownloaderMiddleware": 1041,
            "scrapypuppeteer.middleware.PuppeteerServiceDownloaderMiddleware": 1042,
        },
        "N_RETRY_RESTORING": 3,
        "RESTORING_LENGTH": 2,
    }
    name = "dead_context"

    def start_requests(self):
        urls = [
            "https://www.google.com/recaptcha/api2/demo",
            "https://scrapy.org",
            "https://pptr.dev",
        ]

        for url in urls:
            yield PuppeteerRequest(
                url,
                callback=self.click_on_navigation,
                errback=self.errback,
                close_page=False,
                meta={"recover_context": True},
            )

    async def click_on_navigation(self, response: PuppeteerResponse):
        await sleep(4)

        click = Click(
            "#__docusaurus > nav > div.navbar__inner > div:nth-child(1) > a:nth-child(3)"
        )
        yield response.follow(
            click, callback=self.click_back, errback=self.errback, close_page=False
        )

    async def click_back(self, response: PuppeteerResponse):
        await sleep(4)

        click = Click(
            "#__docusaurus > nav > div.navbar__inner > div:nth-child(1) > a.navbar__brand > b"
        )
        yield response.follow(
            click, callback=self.goto_api, errback=self.errback, close_page=False
        )

    async def goto_api(self, response):
        await sleep(4)

        yield response.follow(
            GoTo("api/puppeteer.puppeteernode"),
            callback=self.empty_action,
            errback=self.errback,
            close_page=False,
        )

    @staticmethod
    async def empty_action(response, **kwargs):
        await sleep(4)

    @staticmethod
    def errback(failure: Failure):
        print(failure)
