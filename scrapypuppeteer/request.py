from scrapy.http import Request

from scrapypuppeteer.actions import GoTo


class PuppeteerRequest(Request):
    def __init__(self, action, context_id=None, page_id=None,
                 close_page=True, response=None,
                 **kwargs):
        if isinstance(action, str):
            url = action
            options = kwargs.pop('options', None)
            action = GoTo(url, options)
        elif isinstance(action, GoTo):
            url = action.url
        elif response is not None:
            url = response.url
            kwargs['dont_filter'] = True
        else:
            raise ValueError('Request is not a goto-request and does not follow a response')
        super().__init__(url, **kwargs)
        self.action = action
        self.context_id = context_id
        self.page_id = page_id
        self.close_page = close_page
