from typing import Union

from scrapy.http import Request

from scrapypuppeteer.actions import GoTo, PuppeteerServiceAction


class PuppeteerRequest(Request):
    """
    Request to be executed in browser with puppeteer.
    """

    def __init__(self,
                 action: Union[str, PuppeteerServiceAction],
                 context_id: str = None,
                 page_id: str = None,
                 close_page: bool = True,
                 **kwargs):
        """

        :param action: URL or browser action
        :param context_id: puppeteer browser context id; if None (default),
                           new incognito context will be created
        :param page_id: puppeteer browser page id; if None (default), new
                        page will be opened in given context
        :param close_page: whether to close page after request completion;
                           set to False, if you want to continue interacting
                           with the page
        :param kwargs:
        """
        url = kwargs.pop('url', None)
        if isinstance(action, str):
            url = action
            navigation_options = kwargs.pop('navigation_options', None)
            wait_options = kwargs.pop('wait_options', None)
            action = GoTo(url, navigation_options=navigation_options, wait_options=wait_options)
        elif isinstance(action, GoTo):
            url = action.url
        elif not isinstance(action, PuppeteerServiceAction):
            raise ValueError('Undefined browser action')
        if url is None:
            raise ValueError('Request is not a goto-request and does not follow a response')
        super().__init__(url, **kwargs)
        self.action = action
        self.context_id = context_id
        self.page_id = page_id
        self.close_page = close_page

    def replace(self, *args, **kwargs):
        for x in ['action', 'context_id', 'page_id', 'close_page']:
            kwargs.setdefault(x, getattr(self, x))
        return super().replace(*args, **kwargs)
