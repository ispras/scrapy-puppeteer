from typing import Union

from scrapy.http import Response, TextResponse

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import GoTo, PuppeteerServiceAction


class PuppeteerResponse(Response):

    attributes: tuple[str, ...] = Response.attributes + (
        'url',
        'puppeteer_request',
        'context_id',
        'page_id'
    )
    """
        A tuple of :class:`str` objects containing the name of all public
        attributes of the class that are also keyword parameters of the
        ``__init__`` method.

        Currently used by :meth:`PuppeteerResponse.replace`.
    """

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
               accumulate_meta: bool = False,
               **kwargs) -> PuppeteerRequest:
        """
        Execute action in same browser page.

        :param action: URL (maybe relative) or browser action.
        :param close_page: whether to close page after request completion
        :param accumulate_meta: whether to accumulate meta from response
        :param kwargs:
        :return:
        """
        page_id = None if self.puppeteer_request.close_page else self.page_id
        if isinstance(action, str):
            action = self.urljoin(action)
        elif isinstance(action, GoTo):
            action.url = self.urljoin(action.url)
        else:
            kwargs['url'] = self.url
            kwargs['dont_filter'] = True
        if accumulate_meta:
            kwargs['meta'] = self.meta | kwargs.pop('meta', {})
        return PuppeteerRequest(action,
                                context_id=self.context_id, page_id=page_id,
                                close_page=close_page, **kwargs)


class PuppeteerHtmlResponse(PuppeteerResponse, TextResponse):
    """
    scrapy.TextResponse capturing state of a page in browser.
    Additionally, exposes received html and cookies via corresponding attributes.
    """

    attributes: tuple[str, ...] = PuppeteerResponse.attributes + (
        'html',
        'cookies'
    )
    """
        A tuple of :class:`str` objects containing the name of all public
        attributes of the class that are also keyword parameters of the
        ``__init__`` method.

        Currently used by :meth:`PuppeteerResponse.replace`.
    """

    def __init__(self, url, puppeteer_request, context_id, page_id, **kwargs):
        self.html = kwargs.pop('html')
        self.cookies = kwargs.pop('cookies')
        kwargs.setdefault('body', self.html)
        kwargs.setdefault('encoding', 'utf-8')
        kwargs.setdefault('headers', {}).setdefault('Content-Type', 'text/html')
        super().__init__(url, puppeteer_request, context_id, page_id, **kwargs)


class PuppeteerScreenshotResponse(PuppeteerResponse):
    """
    Response for Screenshot action.
    Screenshot is available via self.screenshot as base64 encoded string.
    """

    attributes: tuple[str, ...] = PuppeteerResponse.attributes + (
        'screenshot',
    )

    def __init__(self, url, puppeteer_request, context_id, page_id, **kwargs):
        self.screenshot = kwargs.pop('screenshot')
        super().__init__(url, puppeteer_request, context_id, page_id, **kwargs)


class PuppeteerJsonResponse(PuppeteerResponse):
    """
    Response for CustomJsAction and RecaptchaSolver.
    Result is available via self.data object.
    """

    attributes: tuple[str, ...] = PuppeteerResponse.attributes + (
        'data',
    )

    def __init__(self, url, puppeteer_request, context_id, page_id, **kwargs):
        headers = {'Content-Type': 'application/json'}
        request = kwargs['request']
        self.data = kwargs
        super().__init__(url, puppeteer_request, context_id, page_id,
                         headers=headers, request=request)

    def replace(self, *args, **kwargs):
        """
            Create a new PuppeteerJsonResponse object with the same attributes
            except for those given new values
        """
        for attr in self.attributes:
            kwargs.setdefault(attr, getattr(self, attr))

        kwargs = {
            **kwargs.pop('data'),
            **kwargs
        }

        cls = kwargs.pop("cls", self.__class__)
        return cls(*args, **kwargs)
