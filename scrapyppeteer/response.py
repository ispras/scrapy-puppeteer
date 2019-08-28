from scrapy.http import TextResponse

from scrapyppeteer.request import PyppeteerRequest


class PyppeteerResponse(TextResponse):
    def __init__(self, url, context_id=None, page_id=None, **kwargs):
        super().__init__(url, **kwargs)
        self.context_id = context_id
        self.page_id = page_id

    def follow(self, action, **kwargs):
        return PyppeteerRequest(action, self.context_id, self.page_id, **kwargs)
