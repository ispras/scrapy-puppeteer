import scrapy
from scrapy.http import HtmlResponse
from scrapy.loader import ItemLoader
from scrapy.loader.processors import TakeFirst

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import Goto, Scroll


class EcommerceSiteSpider(scrapy.Spider):
    # def start_requests(self):
    #     yield PuppeteerRequest(Goto('https://meduza.io'), callback=self.parse_main_page)

    @staticmethod
    def extract_items(list_page_response):
        for item_selector in list_page_response.css('div.row div.thumbnail'):
            yield {
                'link': item_selector.css('a.title::attr(href)').get(),
                'title': item_selector.css('a.title::attr(title)').get(),
                'price': item_selector.css('h4.price::text').get(),
                'description': item_selector.css('p.description::text').get(),
                'rating': len(item_selector.css('span.glyphicon-star')),
                'reviews_count': int(item_selector
                                     .css('.ratings p.pull-right::text')
                                     .re_first('\d+'))
            }

    @staticmethod
    def extract_item(detail_page_response):
        yield {
            'link': detail_page_response.url,
            'title': detail_page_response.css('h4.price + h4::text').get(),
            'price': detail_page_response.css('h4.price::text').get(),
            'description': detail_page_response.css('p.description::text').get(),
            'rating': len(detail_page_response.css('span.glyphicon-star')),
            'reviews_count': int(detail_page_response
                                 .css('.ratings::text')
                                 .re_first('\d+'))
        }


class ScrollSpider(EcommerceSiteSpider):
    name = 'e-commerce-scroll'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_url = 'https://webscraper.io/test-sites/e-commerce/scroll/computers/laptops'
        self.seen_item_links = set()

    def start_requests(self):
        yield PuppeteerRequest(Goto(self.start_url), callback=self.process_list_page)

    def process_list_page(self, response):
        items = self.extract_items(response)
        new_items = [i for i in items if i['link'] not in self.seen_item_links]
        if new_items:
            for item in new_items:
                self.seen_item_links.add(item['link'])
                yield item
            yield response.follow(Scroll(wait_options={'selectorOrTimeout': 5000}),
                                  callback=self.process_list_page)
