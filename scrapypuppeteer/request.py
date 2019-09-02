from scrapy.http import Request

from scrapypuppeteer.actions import Goto


class PuppeteerRequest(Request):
    def __init__(self, action, context_id=None, page_id=None,
                 close_page=False, close_context=False, response=None,
                 **kwargs):
        if isinstance(action, Goto):
            url = action.url
        elif response is not None:
            url = response.url
        else:
            raise ValueError('Request is not a goto-request and does not follow a response')
        super().__init__(url, **kwargs)
        self.action = action
        self.context_id = context_id
        self.page_id = page_id
        self.close_page = close_page
        self.close_context = close_context
