import logging

from scrapy.crawler import Crawler
from scrapy.exceptions import IgnoreRequest, NotConfigured

from scrapypuppeteer.actions import (
    Click,
    CustomJsAction,
    RecaptchaSolver,
    Screenshot,
    Scroll,
)
from scrapypuppeteer.request import PuppeteerRequest
from scrapypuppeteer.response import PuppeteerHtmlResponse, PuppeteerResponse

recaptcha_logger = logging.getLogger(__name__)


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
                    f"Submit selector must be str or Click, got {type(submit_selector)}"
                )
        return cls(recaptcha_solving, submit_selectors)

    def process_request(self, request, spider):
        if request.meta.get("dont_recaptcha", False):
            return None

        if isinstance(request, PuppeteerRequest):
            if request.close_page and not request.meta.get(
                "_captcha_submission", False
            ):
                request.close_page = False
                request.dont_filter = True
                self._page_closing.add(request)
                return request
        return None

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

        if isinstance(
            puppeteer_request.action,
            (Screenshot, Scroll, CustomJsAction, RecaptchaSolver),
        ):
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
            recaptcha_logger.log(
                level=logging.INFO,
                msg=f"Found {len(response.recaptcha_data['captchas'])} captcha "
                f"but did not solve due to argument",
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
