import scrapy
from twisted.python.failure import Failure

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import GoTo, Screenshot
from scrapypuppeteer.response import PuppeteerResponse, PuppeteerScreenshotResponse

import base64


class AutoRecaptchaSpider(scrapy.Spider):
    """
    Current settings for RecaptchaMiddleware:
        RECAPTCHA_ACTIVATION = True
        RECAPTCHA_SOLVING = True
        RECAPTCHA_SUBMIT_SELECTORS = {
            'www.google.com/recaptcha/api2/demo': '#recaptcha-demo-submit',
        }
    """

    name = "auto_recaptcha"

    start_urls = ["https://www.google.com/recaptcha/api2/demo"]

    def start_requests(self):
        for url in self.start_urls:
            action = GoTo(url=url)
            yield PuppeteerRequest(action=action, callback=self.parse_html, errback=self.error, close_page=False)

    def parse_html(self, response: PuppeteerResponse, **kwargs):
        with open(f"recaptcha_page.html", 'wb') as f:
            f.write(response.body)
        action = Screenshot(options={
            'full_page': True,
        })
        yield response.follow(action,
                              callback=self.make_screenshot,
                              errback=self.error,
                              close_page=True)

    def make_screenshot(self, response: PuppeteerScreenshotResponse, **kwargs):
        data = response.screenshot  # Note that data is string containing bytes, don't forget to decode them!
        with open("imageToSave.png", "wb") as fh:
            fh.write(base64.b64decode(data))

    @staticmethod
    def error(failure: Failure):
        print(f"We are in error function!")
