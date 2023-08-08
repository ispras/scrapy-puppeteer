from typing import List, Union

from scrapy.http import Request

from scrapypuppeteer.actions import GoTo, PuppeteerServiceAction


class PuppeteerRequest(Request):
    """
    Request to be executed in browser with puppeteer.
    """

    attributes: tuple[str, ...] = Request.attributes + (
        'action',
        'context_id',
        'page_id',
        'close_page',
        'include_headers'
    )
    """
        A tuple of :class:`str` objects containing the name of all public
        attributes of the class that are also keyword parameters of the
        ``__init__`` method.

        Currently used by :meth:`PuppeteerRequest.replace`
    """

    def __init__(self,
                 action: Union[str, PuppeteerServiceAction],
                 context_id: str = None,
                 page_id: str = None,
                 close_page: bool = True,
                 include_headers: Union[bool, List[str]] = None,
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
        :param include_headers: determines which headers will be sent to remote
                                site by puppeteer: either True (all headers),
                                False (no headers), list of header names
                                or None (default, let middleware decide)
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
        self.include_headers = include_headers

    def replace(self, *args, **kwargs):
        # TODO: possibly to delete method
        for x in self.attributes:
            kwargs.setdefault(x, getattr(self, x))
        cls = kwargs.pop("cls", self.__class__)
        return cls(*args, **kwargs)

    # def __repr__(self):
    #     return f"<{self.action.endpoint.upper()} {self.url}>"
    #
    # def __str__(self):
    #     return self.__repr__()
