import scrapy
from twisted.python.failure import Failure

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import GoTo, RecaptchaSolver
from scrapypuppeteer.response import PuppeteerResponse


class RecaptchaSpider(scrapy.Spider):
    name = "recaptcha"

    start_urls = ["https://www.google.com/recaptcha/api2/demo"]

    def start_requests(self):
        for url in self.start_urls:
            action = GoTo(url=url)
            yield PuppeteerRequest(action=action, callback=self.solve_recaptcha, errback=self.error, close_page=False)

    def solve_recaptcha(self, response: PuppeteerResponse, **kwargs):
        action = RecaptchaSolver('#recaptcha-demo-submit')
        yield response.follow(action=action, callback=self.parse, errback=self.error, close_page=False)

    def parse(self, response: PuppeteerResponse, **kwargs):
        with open(f"html/{response.url.replace('/', '_')}.html", 'w') as f:
            f.write(str(response.body).strip("b'"))

    @staticmethod
    def error(failure: Failure):
        try:
            print(failure)
            response = failure.value.response
        except BaseException as e:
            print(f"SOMETHING BAD HAPPENED!")
            print(e)
        else:
            with open(f"html/{response.url.replace('/', '_')}.html", 'w') as f:
                f.write(repr(response.body))
