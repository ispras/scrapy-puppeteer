import scrapy

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import GoTo, Scroll, Click


class EcommerceSiteSpider(scrapy.Spider):

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


class AjaxPaginationSpider(EcommerceSiteSpider):
    name = 'e-commerce-ajax'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_url = 'https://webscraper.io/test-sites/e-commerce/ajax/computers/laptops'
        self.next_page_ix = 1

    def start_requests(self):
        yield PuppeteerRequest(GoTo(self.start_url),
                               close_page=False,
                               callback=self.process_list_page)

    def process_list_page(self, response):
        yield from self.extract_items(response)
        self.next_page_ix += 1
        next_page_selector = f'button[data-id="{self.next_page_ix}"]'
        if response.css(next_page_selector):
            yield response.follow(Click(next_page_selector,
                                        wait_options={'selectorOrTimeout': 3000}),
                                  close_page=False,
                                  callback=self.process_list_page)


class MoreSpider(EcommerceSiteSpider):
    name = 'e-commerce-more'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_url = 'https://webscraper.io/test-sites/e-commerce/more/computers/laptops'
        self.seen_item_links = set()

    def start_requests(self):
        yield PuppeteerRequest(GoTo(self.start_url),
                               close_page=False,
                               callback=self.process_list_page)

    def process_list_page(self, response):
        for item in self.extract_items(response):
            if item['link'] not in self.seen_item_links:
                self.seen_item_links.add(item['link'])
                yield item
        more_selector = '.ecomerce-items-scroll-more'
        if response.css(more_selector):
            yield response.follow(Click(more_selector,
                                        wait_options={'selectorOrTimeout': 3000}),
                                  close_page=False,
                                  callback=self.process_list_page)


class ScrollSpider(EcommerceSiteSpider):
    name = 'e-commerce-scroll'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_url = 'https://webscraper.io/test-sites/e-commerce/scroll/computers/laptops'
        self.seen_item_links = set()

    def start_requests(self):
        yield PuppeteerRequest(GoTo(self.start_url),
                               close_page=False,
                               callback=self.process_list_page)

    def process_list_page(self, response):
        items = self.extract_items(response)
        new_items = [i for i in items if i['link'] not in self.seen_item_links]
        if new_items:
            for item in new_items:
                self.seen_item_links.add(item['link'])
                yield item
            yield response.follow(Scroll(wait_options={'selectorOrTimeout': 3000}),
                                  close_page=False,
                                  callback=self.process_list_page)
