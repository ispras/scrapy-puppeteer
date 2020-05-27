from typing import Union
from urllib.parse import urljoin

from scrapy.http import Response, TextResponse

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import GoTo, PuppeteerServiceAction


class PuppeteerResponse(Response):
    def __init__(self,
                 url: str,
                 puppeteer_request: PuppeteerRequest,
                 context_id: str,
                 page_id: str,
                 **kwargs):
        self.puppeteer_request = puppeteer_request
        self.context_id = context_id
        self.page_id = page_id
        super().__init__(url, **kwargs)

    def follow(self,
               action: Union[str, PuppeteerServiceAction],
               close_page=True,
               **kwargs) -> PuppeteerRequest:
        """
        Execute action in same browser page.

        :param action: URL (may be relative) or browser action.
        :param close_page: whether to close page after request completion
        :param kwargs:
        :return:
        """
        page_id = None if self.puppeteer_request.close_page else self.page_id
        if isinstance(action, str):
            action = urljoin(self.url, action)
        elif isinstance(action, GoTo):
            action.url = urljoin(self.url, action.url)
        return PuppeteerRequest(action, context_id=self.context_id, page_id=page_id,
                                close_page=close_page, response=self, **kwargs)


class PuppeteerHtmlResponse(PuppeteerResponse, TextResponse):
    """
    scrapy.TextResponse capturing state of a page in browser.
    Additionally exposes received html and cookies via corresponding attributes.
    """
    def __init__(self, url, puppeteer_request, context_id, page_id, **kwargs):
        self.html = kwargs.pop('html')
        self.cookies = kwargs.pop('cookies')
        kwargs.setdefault('body', self.html)
        kwargs.setdefault('encoding', 'utf-8')
        super().__init__(url, puppeteer_request, context_id, page_id, **kwargs)


class PuppeteerJsonResponse(PuppeteerResponse):
    """
    Response for CustomJsAction.
    Result is available via self.data object.
    """
    def __init__(self, url, puppeteer_request, context_id, page_id, **kwargs):
        self.data = kwargs
        super().__init__(url, puppeteer_request, context_id, page_id)


class PuppeteerScreenshotResponse(PuppeteerResponse):
    """
    Response for Screenshot action.
    Screenshot is available via self.screenshot as base64 encoded string.
    """
    def __init__(self, url, puppeteer_request, context_id, page_id, **kwargs):
        self.screenshot = kwargs.get('screenshot')
        super().__init__(url, puppeteer_request, context_id, page_id, **kwargs)
