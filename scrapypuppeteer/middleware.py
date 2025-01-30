import logging
from collections import defaultdict
from typing import List, Union

from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.exceptions import IgnoreRequest, NotConfigured

from scrapypuppeteer.actions import (
    Click,
    CustomJsAction,
    RecaptchaSolver,
    Screenshot,
    Scroll,
)
from scrapypuppeteer.browser_managers import BrowserManager
from scrapypuppeteer.browser_managers.playwright_browser_manager import (
    PlaywrightBrowserManager,
)
from scrapypuppeteer.browser_managers.pyppeteer_browser_manager import (
    PyppeteerBrowserManager,
)
from scrapypuppeteer.browser_managers.service_browser_manager import (
    ServiceBrowserManager,
)
from scrapypuppeteer.request import ActionRequest, CloseContextRequest, PuppeteerRequest
from scrapypuppeteer.response import (
    PuppeteerHtmlResponse,
    PuppeteerResponse,
)


class PuppeteerServiceDownloaderMiddleware:
    """
    This downloader middleware converts PuppeteerRequest instances to
    Puppeteer service API requests and then converts its responses to
    PuppeteerResponse instances. Additionally, it tracks all browser contexts
    that spider uses and performs cleanup request to service right before
    spider is closed.

        Additionally, the middleware uses these meta-keys, do not use them, because their changing
    could possibly (almost probably) break determined behaviour:
    'puppeteer_request', 'dont_obey_robotstxt', 'proxy'

    Settings:

    PUPPETEER_SERVICE_URL (str)
    Service URL, e.g. 'http://localhost:3000'

    PUPPETEER_INCLUDE_HEADERS (bool|list[str])
    Determines which request headers will be sent to remote site by puppeteer service.
    Either True (all headers), False (no headers) or list of header names.
    May be overridden per request.
    By default, only cookies are sent.

    PUPPETEER_INCLUDE_META (bool)
    Determines whether to send or not user's meta attached by user.
    Default to False.
    """

    SERVICE_URL_SETTING = "PUPPETEER_SERVICE_URL"
    INCLUDE_HEADERS_SETTING = "PUPPETEER_INCLUDE_HEADERS"
    SERVICE_META_SETTING = "PUPPETEER_INCLUDE_META"
    DEFAULT_INCLUDE_HEADERS = ["Cookie"]  # TODO send them separately

    EXECUTION_METHOD_SETTING = "EXECUTION_METHOD"

    service_logger = logging.getLogger(__name__)

    def __init__(
        self,
        crawler: Crawler,
        service_url: str,
        include_headers: Union[bool, List[str]],
        include_meta: bool,
        browser_manager: BrowserManager,
    ):
        self.service_base_url = service_url
        self.include_headers = include_headers
        self.include_meta = include_meta
        self.crawler = crawler
        self.used_contexts = defaultdict(set)
        self.browser_manager = browser_manager

    @classmethod
    def from_crawler(cls, crawler):
        service_url = crawler.settings.get(cls.SERVICE_URL_SETTING)
        if cls.INCLUDE_HEADERS_SETTING in crawler.settings:
            try:
                include_headers = crawler.settings.getbool(cls.INCLUDE_HEADERS_SETTING)
            except ValueError:
                include_headers = crawler.settings.getlist(cls.INCLUDE_HEADERS_SETTING)
        else:
            include_headers = cls.DEFAULT_INCLUDE_HEADERS
        include_meta = crawler.settings.getbool(cls.SERVICE_META_SETTING, False)

        execution_method = crawler.settings.get(
            cls.EXECUTION_METHOD_SETTING, "PUPPETEER"
        ).lower()

        if execution_method == "pyppeteer":
            browser_manager = PyppeteerBrowserManager()
        elif execution_method == "puppeteer":
            browser_manager = ServiceBrowserManager(
                service_url, include_meta, include_headers, crawler
            )
        elif execution_method == "playwright":
            browser_manager = PlaywrightBrowserManager()
        else:
            raise NameError("Wrong EXECUTION_METHOD")

        middleware = cls(
            crawler, service_url, include_headers, include_meta, browser_manager
        )
        crawler.signals.connect(
            middleware.browser_manager.close_used_contexts, signal=signals.spider_idle
        )
        return middleware

    def process_request(self, request, spider):
        return self.browser_manager.process_request(request)

    def process_response(self, request, response, spider):
        return self.browser_manager.process_response(self, request, response, spider)


class PuppeteerRecaptchaDownloaderMiddleware:
    """
        This middleware is supposed to solve recaptcha on the page automatically.
    If there is no captcha on the page then this middleware will do nothing
    on the page, so your 2captcha balance will remain the same.
    It can submit recaptcha if "submit button" is provided.
    It will not "submit" captcha if there is no submit-selector.

        If you want to turn Recaptcha solving off on the exact request provide
    meta-key 'dont_recaptcha' with True value. The middleware will skip the request
    through itself.

        The middleware uses additionally these meta-keys, do not use them, because their changing
    could possibly (almost probably) break determined behaviour:
    '_captcha_submission', '_captcha_solving'

        Settings:

    RECAPTCHA_ACTIVATION: bool = True - activates or not the middleware (if not - raises NotConfigured)
    RECAPTCHA_SOLVING: bool = True - whether solve captcha automatically or not
    RECAPTCHA_SUBMIT_SELECTORS: str | dict = {} - dictionary consisting of domains and
        these domains' submit selectors, e.g.
            'www.google.com/recaptcha/api2/demo': '#recaptcha-demo-submit'
        it could be also squeezed to
            'ecaptcha/api2/de': '#recaptcha-demo-submit'
        also you can use not just strings but Click actions with required parameters:
            'ogle.com/recaptcha': Click('#recaptcha-demo-submit')
        In general - domain is a unique identifying string which is contained in web-page url
        If there is no button to submit recaptcha then provide empty string to a domain.
        This setting can also be a string. If so the middleware will only click the button
        related to this selector.
        This setting can also be unprovided. In this case every web-page you crawl is supposed to be
        without submit button, or you manually do it yourself.
    """

    MIDDLEWARE_ACTIVATION_SETTING = "RECAPTCHA_ACTIVATION"
    RECAPTCHA_SOLVING_SETTING = "RECAPTCHA_SOLVING"
    SUBMIT_SELECTORS_SETTING = "RECAPTCHA_SUBMIT_SELECTORS"

    def __init__(self, recaptcha_solving: bool, submit_selectors: dict):
        self.submit_selectors = submit_selectors
        self.recaptcha_solving = recaptcha_solving
        self._page_responses = dict()
        self._page_closing = set()

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        activation = crawler.settings.get(cls.MIDDLEWARE_ACTIVATION_SETTING, True)
        if not activation:
            raise NotConfigured
        recaptcha_solving = crawler.settings.get(cls.RECAPTCHA_SOLVING_SETTING, True)

        try:
            submit_selectors = crawler.settings.getdict(
                cls.SUBMIT_SELECTORS_SETTING, dict()
            )
        except ValueError:
            submit_selectors = {
                "": crawler.settings.get(cls.SUBMIT_SELECTORS_SETTING, "")
            }
        except Exception as exception:
            raise ValueError(
                f"Wrong argument(s) inside {cls.SUBMIT_SELECTORS_SETTING}: {exception}"
            )

        for key in submit_selectors.keys():
            submit_selector = submit_selectors[key]
            if isinstance(submit_selector, str):
                submit_selectors[key] = Click(selector=submit_selector)
            elif not isinstance(submit_selector, Click):
                raise TypeError(
                    "Submit selector must be str or Click,"
                    f"but {type(submit_selector)} provided"
                )
        return cls(recaptcha_solving, submit_selectors)

    @staticmethod
    def is_recaptcha_producing_action(action) -> bool:
        return not isinstance(
            action,
            (Screenshot, Scroll, CustomJsAction, RecaptchaSolver),
        )

    def process_request(self, request, **_):
        if request.meta.get("dont_recaptcha", False):
            return None

        # Checking if we need to close page after action
        if isinstance(request, PuppeteerRequest):
            if self.is_recaptcha_producing_action(request.action):
                if request.close_page and not request.meta.get(
                    "_captcha_submission", False
                ):
                    request.close_page = False
                    request.dont_filter = True
                    self._page_closing.add(request)
                    return request

    def process_response(self, request, response, spider):
        if not isinstance(
            response, PuppeteerResponse
        ):  # We only work with PuppeteerResponses
            return response

        puppeteer_request = response.puppeteer_request
        if puppeteer_request.meta.get("dont_recaptcha", False):  # Skip such responses
            return response

        if puppeteer_request.meta.pop(
            "_captcha_submission", False
        ):  # Submitted captcha
            return self.__gen_response(response)

        if puppeteer_request.meta.pop("_captcha_solving", False):
            # RECaptchaSolver was called by recaptcha middleware
            return self._submit_recaptcha(request, response, spider)

        if not self.is_recaptcha_producing_action(puppeteer_request.action):
            # No recaptcha after these actions
            return response

        # Any puppeteer response besides PuppeteerRecaptchaSolverResponse
        return self._solve_recaptcha(request, response)

    def _solve_recaptcha(self, request, response):
        self._page_responses[response.page_id] = (
            response  # Saving main response to return it later
        )

        recaptcha_solver = RecaptchaSolver(
            solve_recaptcha=self.recaptcha_solving,
            close_on_empty=self.__is_closing(response, remove_request=False),
            navigation_options={"waitUntil": "domcontentloaded"},
        )
        return response.follow(
            recaptcha_solver,
            callback=request.callback,
            cb_kwargs=request.cb_kwargs,
            errback=request.errback,
            meta={"_captcha_solving": True},
            close_page=False,
        )

    def _submit_recaptcha(self, request, response, spider):
        if not response.puppeteer_request.action.solve_recaptcha:
            spider.log(
                message=f"Found {len(response.recaptcha_data['captchas'])} captcha "
                f"but did not solve due to argument",
                level=logging.INFO,
            )
            return self.__gen_response(response)
        # Click "submit button"?
        if response.recaptcha_data["captchas"] and self.submit_selectors:
            # We need to click "submit button"
            for domain, submitting in self.submit_selectors.items():
                if domain in response.url:
                    if not submitting.selector:
                        return self.__gen_response(response)
                    return response.follow(
                        action=submitting,
                        callback=request.callback,
                        cb_kwargs=request.cb_kwargs,
                        errback=request.errback,
                        close_page=self.__is_closing(response),
                        meta={"_captcha_submission": True},
                    )
            raise IgnoreRequest(
                "No submit selector found to click on the page but captcha found"
            )
        return self.__gen_response(response)

    def __gen_response(self, response):
        main_response_data = dict()
        main_response_data["page_id"] = (
            None if self.__is_closing(response) else response.puppeteer_request.page_id
        )

        main_response = self._page_responses.pop(response.page_id)

        if isinstance(main_response, PuppeteerHtmlResponse):
            if isinstance(response.puppeteer_request.action, RecaptchaSolver):
                main_response_data["body"] = response.html
            elif isinstance(response.puppeteer_request.action, Click):
                main_response_data["body"] = response.body

        return main_response.replace(**main_response_data)

    def __is_closing(self, response, remove_request: bool = True) -> bool:
        main_request = self._page_responses[response.page_id].puppeteer_request
        close_page = main_request in self._page_closing
        if close_page and remove_request:
            self._page_closing.remove(main_request)
        return close_page
