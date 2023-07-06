import scrapy

from twisted.python.failure import Failure
from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import GoTo, RecaptchaSolver, Click
from scrapypuppeteer.response import PuppeteerResponse, PuppeteerJsonResponse


class RecaptchaSpider(scrapy.Spider):
    name = "recaptcha"

    start_urls = ["https://www.google.com/recaptcha/api2/demo"]

    def start_requests(self):
        for url in self.start_urls:
            action = GoTo(url=url)
            yield PuppeteerRequest(action=action, callback=self.solve_recaptcha, errback=self.error, close_page=False)

    def solve_recaptcha(self, response: PuppeteerResponse, **kwargs):
        action = RecaptchaSolver()
        yield response.follow(action=action, callback=self.submit_recaptcha, errback=self.error, close_page=False)

    def submit_recaptcha(self, response: PuppeteerJsonResponse, **kwargs):
        with open("metaData/meta.txt", 'w') as f:
            print(response.data.get('recaptcha_data', None), file=f)
        action = Click('#recaptcha-demo-submit')
        yield response.follow(action=action, callback=self.parse, errback=self.error, close_page=False)

    def parse(self, response: PuppeteerResponse, **kwargs):
        with open(f"html/{response.url.replace('/', '_')}.html", 'w') as f:
            f.write(repr(response.body))

    @staticmethod
    def error(failure: Failure):
        print(f"We are in error function!")
