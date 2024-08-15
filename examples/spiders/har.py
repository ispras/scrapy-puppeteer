import scrapy
from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import Har


def write_to_file(file_path, content):
    with open(file_path, "a", encoding="utf-8") as file:
        file.write(content)


class HarSpider(scrapy.Spider):
    name = "har"
    start_urls = ["https://github.com/pyppeteer/pyppeteer"]

    def start_requests(self):
        for url in self.start_urls:
            yield PuppeteerRequest(
                url, callback=self.har, close_page=False, har_recording=True
            )

    def har(self, response):
        yield response.follow(
            Har(),
            close_page=False,
            callback=self.save_har,
        )

    def save_har(self, response):
        write_to_file("result.har", response.har)
