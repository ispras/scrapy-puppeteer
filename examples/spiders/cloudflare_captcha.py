import scrapy
from scrapy.http import TextResponse
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.python.failure import Failure

from scrapypuppeteer import PuppeteerCaptchaSolverResponse, PuppeteerRequest
from scrapypuppeteer.actions import CaptchaSolver, Compose, GoTo


class CloudflareCaptchaSpider(scrapy.Spider):
    name = "cloudflare_captcha"
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapypuppeteer.middleware.PuppeteerServiceDownloaderMiddleware": 1042,
        },
    }

    def start_requests(self):
        urls = [
            "https://2captcha.com/demo/cloudflare-turnstile-challenge",
        ]

        for url in urls:
            compose_action = Compose(
                GoTo(url, navigation_options={"waitUntil": "networkidle2"}),
                # It's essential to wait for smth before solving Cloudflare captcha since it must be rendered on the page
                CaptchaSolver(solve_cloudflare=True, solve_recaptcha=None),
            )
            yield PuppeteerRequest(
                compose_action, dont_filter=True, callback=self.parse, close_page=False
            )

    async def parse(self, response: PuppeteerCaptchaSolverResponse):
        assert "Captcha is passed successfully!" in response.text, (
            "No successful text in response"
        )
        print(response.cloudflare_captcha_data)

    @staticmethod
    def errback(failure: Failure):
        value: HttpError = failure.value
        response: TextResponse = value.response
        puppeteer_request = response.request.meta.get("puppeteer_request")
        print(puppeteer_request.url)
