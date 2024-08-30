import base64
import logging

import scrapy
from twisted.python.failure import Failure

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import Click, GoTo, RecaptchaSolver, Screenshot
from scrapypuppeteer.response import PuppeteerResponse, PuppeteerScreenshotResponse


class ManualRecaptchaSpider(scrapy.Spider):
    name = "manual_recaptcha"

    start_urls = ["https://www.google.com/recaptcha/api2/demo"]

    def start_requests(self):
        for url in self.start_urls:
            action = GoTo(url=url)
            yield PuppeteerRequest(
                action=action,
                callback=self.solve_recaptcha,
                errback=self.error,
                close_page=False,
            )

    def solve_recaptcha(self, response: PuppeteerResponse, **kwargs):
        action = RecaptchaSolver()
        yield response.follow(
            action=action,
            callback=self.submit_recaptcha,
            errback=self.error,
            close_page=False,
        )

    def submit_recaptcha(self, response, **kwargs):
        action = Click("#recaptcha-demo-submit")
        yield response.follow(
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
