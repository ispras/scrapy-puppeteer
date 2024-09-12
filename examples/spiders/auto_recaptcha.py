import base64
import logging

import scrapy
from twisted.python.failure import Failure

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import GoTo, Screenshot
from scrapypuppeteer.response import PuppeteerResponse, PuppeteerScreenshotResponse


class AutoRecaptchaSpider(scrapy.Spider):
    name = "auto_recaptcha"

    start_urls = ["https://www.google.com/recaptcha/api2/demo"]

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapypuppeteer.middleware.PuppeteerRecaptchaDownloaderMiddleware": 1041,
            "scrapypuppeteer.middleware.PuppeteerServiceDownloaderMiddleware": 1042,
        },
        "PUPPETEER_INCLUDE_META": True,
        "RECAPTCHA_ACTIVATION": True,
        "RECAPTCHA_SOLVING": True,
        "RECAPTCHA_SUBMIT_SELECTORS": {
            "www.google.com/recaptcha/api2/demo": "#recaptcha-demo-submit",
        },
    }

    def start_requests(self):
        for url in self.start_urls:
            action = GoTo(url=url)
            yield PuppeteerRequest(
                action=action,
                callback=self.parse_html,
                errback=self.error,
                close_page=False,
            )

    def parse_html(self, response: PuppeteerResponse, **kwargs):
        with open("recaptcha_page.html", "wb") as f:
            f.write(response.body)
        action = Screenshot(
            options={
                "full_page": True,
            }
        )
        yield response.follow(
            action, callback=self.make_screenshot, errback=self.error, close_page=True
        )

    @staticmethod
    def make_screenshot(response: PuppeteerScreenshotResponse, **kwargs):
        data = (
            response.screenshot
        )  # Note that data is string containing bytes, don't forget to decode them!
        with open("imageToSave.png", "wb") as fh:
            fh.write(base64.b64decode(data))

    def error(self, failure: Failure):
        self.log("We are in error function!", level=logging.WARNING)
