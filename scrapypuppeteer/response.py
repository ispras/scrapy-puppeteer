from urllib.parse import urljoin

from scrapy.http import TextResponse

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import Goto


class PuppeteerResponse(TextResponse):
    def __init__(self, url, puppeteer_request, context_id, page_id, **kwargs):
        super().__init__(url, **kwargs)
        self.puppeteer_request = puppeteer_request
        self.context_id = context_id
        self.page_id = page_id

    def follow(self, action, close_page=False, close_context=False, **kwargs):
        page_id = None if self.puppeteer_request.close_page else self.page_id
        if isinstance(action, Goto):
            action.url = urljoin(self.url, action.url)
        return PuppeteerRequest(action, context_id=self.context_id, page_id=page_id,
                                close_page=close_page, response=self, **kwargs)
