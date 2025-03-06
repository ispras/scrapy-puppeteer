import warnings
from typing import Generator, Tuple, Union

import parsel
from scrapy.exceptions import ScrapyDeprecationWarning
from scrapy.http import HtmlResponse, TextResponse
from scrapy.http.response.text import _url_from_selector
from scrapy.link import Link

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import Compose, GoTo, PuppeteerServiceAction


class PuppeteerResponse(TextResponse):
    attributes: Tuple[str, ...] = TextResponse.attributes + (
        "url",
        "puppeteer_request",
        "context_id",
        "page_id",
    )
    """
        A tuple of :class:`str` objects containing the name of all public
        attributes of the class that are also keyword parameters of the
        ``__init__`` method.

        Currently used by :meth:`PuppeteerResponse.replace`.
    """

    def __init__(
        self,
        url: str,
        puppeteer_request: PuppeteerRequest,
        context_id: str,
        page_id: str,
        **kwargs,
    ):
        self.puppeteer_request = puppeteer_request
        self.context_id = context_id
        self.page_id = page_id
        super().__init__(url, **kwargs)

    def follow(
        self,
        action: Union[str, parsel.Selector, Link, PuppeteerServiceAction],
        close_page=True,
        accumulate_meta: bool = False,
        **kwargs,
    ) -> PuppeteerRequest:
        """
        Execute action on the same browser page.

        :param action: URL (maybe relative) or browser action.
        :param close_page: whether to close page after request completion
        :param accumulate_meta: whether to accumulate meta from response
        :param kwargs:
        :return:
        """
        page_id = None if self.puppeteer_request.close_page else self.page_id
        if isinstance(action, str):
            action = self.urljoin(action)
        elif isinstance(action, parsel.Selector):
            action = self.urljoin(_url_from_selector(action))
        elif isinstance(action, Link):
            action = self.urljoin(action.url)
        elif isinstance(action, GoTo):
            action.url = self.urljoin(action.url)
        else:
            kwargs["url"] = self.url
            kwargs["dont_filter"] = True
        if accumulate_meta:
            kwargs["meta"] = {**self.meta, **kwargs.pop("meta", {})}
        return PuppeteerRequest(
            action,
            context_id=self.context_id,
            page_id=page_id,
            close_page=close_page,
            **kwargs,
        )

    def follow_all(
        self,
        actions=None,
        close_page: bool = True,
        accumulate_meta: bool = False,
        css=None,
        xpath=None,
        **kwargs,
    ) -> Generator[PuppeteerRequest, None, None]:
        """
        Execute actions in the same context but in other browser pages.
        Only one of `actions`, `css`, or `xpath` must be specified.`
        Note that original page from which the method was called lasts unaffected.

        :param actions: iterable of PuppeteerActions or selectors
        :param close_page: whether to close page after request completion
        :param accumulate_meta: whether to accumulate meta from response
        :param css: selector
        :param xpath: selector
        :return: Iterable[PuppeteerRequest]
        """

        arguments = [x for x in (actions, css, xpath) if x is not None]
        if len(arguments) != 1:
            raise ValueError(
                "Please supply exactly one of the following arguments: actions, css, xpath"
            )
        if not actions:
            if css:
                actions = self.css(css)
            if xpath:
                actions = self.xpath(xpath)
        else:
            # Ban any PuppeteerAction except GoTo and GoTo-like Compose
            for action in actions:
                if isinstance(action, PuppeteerServiceAction):
                    if isinstance(action, Compose):
                        action = action.actions[0]
                    if not isinstance(action, GoTo):
                        raise TypeError(f"Expected GoTo, got {type(action)}")

        page_id = self.page_id
        for action in actions:
            self.page_id = None  # Substitution of page_id in order to create new page
            try:
                next_request = self.follow(
                    action,
                    close_page=close_page,
                    accumulate_meta=accumulate_meta,
                    **kwargs,
                )
            finally:  # To save the original state of response
                self.page_id = page_id
            yield next_request


class PuppeteerHtmlResponse(PuppeteerResponse, HtmlResponse):
    """
    scrapy.TextResponse capturing state of a page in browser.
    Additionally, exposes received html and cookies via corresponding attributes.
    """

    attributes: Tuple[str, ...] = tuple(
        set(PuppeteerResponse.attributes + HtmlResponse.attributes)
    ) + ("html", "cookies")
    """
        A tuple of :class:`str` objects containing the name of all public
        attributes of the class that are also keyword parameters of the
        ``__init__`` method.

        Currently used by :meth:`PuppeteerResponse.replace`.
    """

    def __init__(self, url, puppeteer_request, context_id, page_id, **kwargs):
        self.html = kwargs.pop("html")
        self.cookies = kwargs.pop("cookies")
        kwargs.setdefault("body", self.html)
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("headers", {}).setdefault("Content-Type", "text/html")
        super().__init__(url, puppeteer_request, context_id, page_id, **kwargs)


class PuppeteerScreenshotResponse(PuppeteerResponse):
    """
    Response for Screenshot action.
    Screenshot is available via self.screenshot as base64 encoded string.
    """

    attributes: Tuple[str, ...] = PuppeteerResponse.attributes + ("screenshot",)

    def __init__(self, url, puppeteer_request, context_id, page_id, **kwargs):
        self.screenshot = kwargs.pop("screenshot")
        super().__init__(url, puppeteer_request, context_id, page_id, **kwargs)


class PuppeteerHarResponse(PuppeteerResponse):
    """
    Response for Har action.
    Har is available via self.har.
    """

    attributes: Tuple[str, ...] = PuppeteerResponse.attributes + ("har",)

    def __init__(self, url, puppeteer_request, context_id, page_id, **kwargs):
        self.har = kwargs.pop("har")
        super().__init__(url, puppeteer_request, context_id, page_id, **kwargs)


class PuppeteerJsonResponse(PuppeteerResponse):
    """
    Response for CustomJsAction.
    Result is available via self.data object.
    """

    attributes: Tuple[str, ...] = PuppeteerResponse.attributes + ("data",)

    def __init__(self, url, puppeteer_request, context_id, page_id, data, **kwargs):
        kwargs["headers"] = {"Content-Type": "application/json"}
        self.data = data
        super().__init__(url, puppeteer_request, context_id, page_id, **kwargs)

    def to_html(self) -> PuppeteerHtmlResponse:
        """
        Tries to converge a PuppeteerJsonResponse to a PuppeteerHtmlResponse.
        For this self.data must be dict.
        Then self.data must have "html" key with a string containing a page content
        and "cookies" key with a list of cookies or None.

        If the .data property does not have at least 1 argument the error is raised.
        """
        if not isinstance(self.data, dict):
            raise TypeError(
                "PuppeteerJsonResponse's .data property must be a dict"
                "to converse it to a PuppeteerHtmlResponse."
            )

        kwargs = dict()
        for attr in PuppeteerResponse.attributes:
            kwargs[attr] = getattr(self, attr)
        kwargs["html"] = self.data["html"]
        kwargs["body"] = kwargs["html"]
        kwargs["cookies"] = self.data["cookies"]
        kwargs["headers"].update({"Content-Type": ["text/html"]})
        kwargs["encoding"] = "utf-8"

        return PuppeteerHtmlResponse(**kwargs)


class PuppeteerRecaptchaSolverResponse(PuppeteerJsonResponse, PuppeteerHtmlResponse):
    """
    Response for RecaptchaSolver.
    Result is available via self.recaptcha_data and self.data["recaptcha_data"]
    (deprecated, to be deleted in next versions) object.
    You can visit
    https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-recaptcha#result-object
    to get information about return value.
    """

    attributes: Tuple[str, ...] = tuple(
        set(PuppeteerHtmlResponse.attributes + PuppeteerJsonResponse.attributes)
    ) + ("recaptcha_data",)

    @property
    def data(self):
        warnings.warn(
            "self.data['recaptcha_data'] is deprecated and staged to remove in next versions. "
            "Use self.recaptcha_data instead.",
            ScrapyDeprecationWarning,
            stacklevel=2,
        )
        return self._data

    @data.setter
    def data(self, value):
        self._data = value

    def __init__(
        self, url, puppeteer_request, context_id, page_id, recaptcha_data, **kwargs
    ):
        kwargs["headers"] = {"Content-Type": "application/json"}
        self._data = {"recaptcha_data": recaptcha_data}
        self.recaptcha_data = recaptcha_data
        super().__init__(
            url, puppeteer_request, context_id, page_id, self._data, **kwargs
        )
