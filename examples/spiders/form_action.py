import scrapy
from scrapypuppeteer import PuppeteerRequest, PuppeteerScreenshotResponse
from scrapypuppeteer.actions import Screenshot, FormAction
import base64


class FormActionSpider(scrapy.Spider):
    name = "form_action"
    start_urls = ["https://www.roboform.com/filling-test-all-fields"]

    def start_requests(self):
        for url in self.start_urls:
            yield PuppeteerRequest(url, callback=self.form_action, close_page=False)

    def form_action(self, response):
        input_mapping = {
            'input[name="02frstname"]': {"value": "SomeName", "delay": 50},
            'input[name="05_company"]': {"value": "SomeCompany", "delay": 100},
            'input[name="06position"]': {"value": "SomePosition", "delay": 100},
        }

        yield response.follow(
            FormAction(input_mapping), close_page=False, callback=self.screenshot
        )

    def screenshot(self, response):
        action = Screenshot(
            options={
                "fullPage": True,
            }
        )
        yield response.follow(action, callback=self.make_screenshot, close_page=False)

    @staticmethod
    def make_screenshot(response: PuppeteerScreenshotResponse, **kwargs):
        data = response.screenshot
        with open(f"screenshot.png", "wb") as fh:
            fh.write(base64.b64decode(data))
