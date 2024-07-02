import json
from typing import Tuple, List, Union

from scrapy.http import Request, Headers

from scrapypuppeteer.actions import GoTo, PuppeteerServiceAction


class ActionRequest(Request):
    """
        Request with puppeteer action parameter and
    beautified representation.
    """

    attributes: Tuple[str, ...] = Request.attributes + ("action",)
    """
        A tuple of :class:`str` objects containing the name of all public
        attributes of the class that are also keyword parameters of the
        ``__init__`` method.
    """

    def __init__(self, url: str, action: Union[str, PuppeteerServiceAction], **kwargs):
        self.action = action
        super().__init__(url, **kwargs)

    def __repr__(self):
        return f"<{self.action.endpoint.upper()} {self.meta.get('puppeteer_request', self).url}>"

    def __str__(self):
        return self.__repr__()


class PuppeteerRequest(ActionRequest):
    """
    Request to be executed in browser with puppeteer.
    """

    attributes: Tuple[str, ...] = ActionRequest.attributes + (
        "context_id",
        "page_id",
        "close_page",
        "include_headers",
    )
    """
        A tuple of :class:`str` objects containing the name of all public
        attributes of the class that are also keyword parameters of the
        ``__init__`` method.

        Currently used by :meth:`PuppeteerRequest.replace`
    """

    def __init__(
        self,
        action: Union[str, PuppeteerServiceAction],
        context_id: str = None,
        page_id: str = None,
        close_page: bool = True,
        include_headers: Union[bool, List[str]] = None,
        **kwargs,
    ):
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
        url = kwargs.pop("url", None)
        if isinstance(action, str):
            url = action
            navigation_options = kwargs.pop("navigation_options", None)
            wait_options = kwargs.pop("wait_options", None)
            action = GoTo(
                url, navigation_options=navigation_options, wait_options=wait_options
            )
        elif isinstance(action, GoTo):
            url = action.url
        elif not isinstance(action, PuppeteerServiceAction):
            raise ValueError("Undefined browser action")
        if url is None:
            raise ValueError(
                "Request is not a goto-request and does not follow a response"
            )
        super().__init__(url, action, **kwargs)
        self.context_id = context_id
        self.page_id = page_id
        self.close_page = close_page
        self.include_headers = include_headers


class CloseContextRequest(Request):
    """
    This request is used to close the browser contexts.

    The response for this request is a regular Scrapy HTMLResponse.
    """

    attributes: Tuple[str, ...] = Request.attributes + ("contexts",)

    def __init__(self, contexts: List, **kwargs):
        """
        :param contexts: list of puppeteer contexts to close.

        :param kwargs: arguments of scrapy.Request.
        """
        self.contexts = contexts
        self.is_valid_url = False

        if "url" in kwargs:
            self.is_valid_url = True
        url = kwargs.pop("url", "://")  # Incorrect url. To be replaced in middleware

        kwargs["method"] = "POST"
        kwargs["headers"] = Headers({"Content-Type": "application/json"})
        kwargs["body"] = json.dumps(self.contexts)

        super().__init__(url, **kwargs)

    def __repr__(self):
        return f"<CLOSE CONTEXT {self.url if self.is_valid_url else 'undefined url'}>"

    def __str__(self):
        return self.__repr__()
