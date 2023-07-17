import scrapy
from twisted.python.failure import Failure

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import GoTo, RecaptchaSolver, Click, Screenshot
from scrapypuppeteer.response import PuppeteerResponse, PuppeteerJsonResponse


class RecaptchaSpider(scrapy.Spider):
    name = "recaptcha"

    start_urls = ["https://www.google.com/recaptcha/api2/demo"]

    def start_requests(self):
        for url in self.start_urls:
            action = GoTo(url=url)
            yield PuppeteerRequest(action=action, callback=self.parse_html, errback=self.error, close_page=False)

    def solve_recaptcha(self, response: PuppeteerResponse, **kwargs):
        # Activate this function and submit_recaptcha
        # if you want to manually proceed recaptcha solving.
        # Don't forget to turn off RecaptchaMiddleware
        action = RecaptchaSolver()
        yield response.follow(action=action, callback=self.submit_recaptcha, errback=self.error, close_page=False)

    def submit_recaptcha(self, response: PuppeteerJsonResponse, **kwargs):
        with open("metaData/meta.txt", 'w') as f:
            print(response.data.get('recaptcha_data', None), file=f)
        action = Click('#recaptcha-demo-submit')
        yield response.follow(action=action, callback=self.parse_html, errback=self.error, close_page=False)

    def parse_html(self, response: PuppeteerResponse | PuppeteerJsonResponse, **kwargs):
        with open(f"html/recaptcha_page.html", 'wb') as f:
            f.write(response.body)
        action = Screenshot(options={
            'full_page': True,
        })
        yield response.follow(action,
                              callback=self.save_image,
                              errback=self.error,
                              close_page=True)

    def save_image(self, response, **kwargs):
        data = response.screenshot  # Note that data is string containing bytes, don't forget to decode them!
        import base64
        with open("imageToSave.png", "wb") as fh:
            fh.write(base64.b64decode(data))

    @staticmethod
    def error(failure: Failure):
        print(f"We are in error function!")
