import scrapy

from scrapyppeteer import PyppeteerRequest, PyppeteerResponse
from scrapyppeteer.actions import goto


class TestSpider(scrapy.Spider):
    name = 'meduza'

    def start_requests(self):
        yield PyppeteerRequest(goto('https://meduza.io', timeout=0), callback=self.parse_main_page)

    def parse_main_page(self, response: PyppeteerResponse):
        for article_url in response.css('a.Link-isInBlockTitle::attr(href)').getall():
            yield response.follow(goto(article_url, timeout=0), callback=self.parse_article)

    def parse_article(self, response: PyppeteerResponse):
        yield {
            'url': response.url,
            'title': response.css('h1::text').get(),
            'text': '\n'.join(response.css('div.GeneralMaterial-article > p::text').getall())
        }
