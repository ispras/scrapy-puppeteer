import json
import logging
from collections import defaultdict
from typing import List, Union
from urllib.parse import urlencode, urljoin

from scrapy import Request, signals
from scrapy.crawler import Crawler
from scrapy.exceptions import IgnoreRequest, NotConfigured
from scrapy.http import Headers, TextResponse

from scrapypuppeteer.actions import Click, GoBack, GoForward, GoTo, RecaptchaSolver, Screenshot, Scroll, CustomJsAction
from scrapypuppeteer.response import PuppeteerResponse, PuppeteerHtmlResponse, PuppeteerScreenshotResponse, PuppeteerJsonResponse
from scrapypuppeteer.request import ActionRequest, PuppeteerRequest


class PuppeteerServiceDownloaderMiddleware:
    """
    This downloader middleware converts PuppeteerRequest instances to
    Puppeteer service API requests and then converts its responses to
    PuppeteerResponse instances. Additionally, it tracks all browser contexts
    that spider uses and performs cleanup request to service once spider
    is closed.

        Additionally, the middleware uses these meta-keys, do not use them, because their changing
    could possibly (almost probably) break determined behaviour:
    'puppeteer_request', 'dont_obey_robotstxt', 'proxy'

    Settings:

    PUPPETEER_SERVICE_URL (str)
    Service URL, e.g. 'http://localhost:3000'

    PUPPETEER_INCLUDE_HEADERS (bool|list[str])
    Determines which request headers will be sent to remote site by puppeteer service.
    Either True (all headers), False (no headers) or list of header names.
    May be overriden per request.
    By default, only cookies are sent.

    PUPPETEER_INCLUDE_META (bool)
    Determines whether to send or not user's meta attached by user.
    Default to False.
    """

    SERVICE_URL_SETTING = 'PUPPETEER_SERVICE_URL'
    INCLUDE_HEADERS_SETTING = 'PUPPETEER_INCLUDE_HEADERS'
    SERVICE_META_SETTING = 'PUPPETEER_INCLUDE_META'
    DEFAULT_INCLUDE_HEADERS = ['Cookie']  # TODO send them separately

    def __init__(self,
                 crawler: Crawler,
                 service_url: str,
                 include_headers: Union[bool, List[str]],
                 include_meta: bool):
        self.service_base_url = service_url
        self.include_headers = include_headers
        self.include_meta = include_meta
        self.crawler = crawler
        self.used_contexts = defaultdict(set)

    @classmethod
    def from_crawler(cls, crawler):
        service_url = crawler.settings.get(cls.SERVICE_URL_SETTING)
        if service_url is None:
            raise ValueError('Puppeteer service URL must be provided')
        if cls.INCLUDE_HEADERS_SETTING in crawler.settings:
            try:
                include_headers = crawler.settings.getbool(cls.INCLUDE_HEADERS_SETTING)
            except ValueError:
                include_headers = crawler.settings.getlist(cls.INCLUDE_HEADERS_SETTING)
        else:
            include_headers = cls.DEFAULT_INCLUDE_HEADERS
        include_meta = crawler.settings.getbool(cls.SERVICE_META_SETTING, False)
        middleware = cls(crawler, service_url, include_headers, include_meta)
        crawler.signals.connect(middleware.close_used_contexts,
                                signal=signals.spider_closed)
        return middleware

    def process_request(self, request, spider):
        if not isinstance(request, PuppeteerRequest):
            return

        action = request.action
        service_url = urljoin(self.service_base_url, action.endpoint)
        service_params = self._encode_service_params(request)
        if service_params:
            service_url += '?' + service_params

        meta = {
            'puppeteer_request': request,
            'dont_obey_robotstxt': True,
            'proxy': None
        }
        if self.include_meta:
            meta = {
                **request.meta,
                **meta
            }

        return ActionRequest(
            url=service_url,
            action=action,
            method='POST',
            headers=Headers({'Content-Type': action.content_type}),
            body=self._serialize_body(action, request),
            dont_filter=True,
            cookies=request.cookies,
            priority=request.priority,
            callback=request.callback,
            cb_kwargs=request.cb_kwargs,
            errback=request.errback,
            meta=meta
        )

    @staticmethod
    def _encode_service_params(request):
        service_params = {}
        if request.context_id is not None:
            service_params['contextId'] = request.context_id
        if request.page_id is not None:
            service_params['pageId'] = request.page_id
        if request.close_page:
            service_params['closePage'] = 1
        return urlencode(service_params)

    def _serialize_body(self, action, request):
        payload = action.payload()
        if action.content_type == 'application/json':
            if isinstance(payload, dict):
                # disallow null values in top-level request parameters
                payload = {k: v for k, v in payload.items() if v is not None}
            proxy = request.meta.get('proxy')
            if proxy:
                payload['proxy'] = proxy
            include_headers = self.include_headers if request.include_headers is None else request.include_headers
            if include_headers:
                headers = request.headers.to_unicode_dict()
                if isinstance(include_headers, list):
                    headers = {h.lower(): headers[h] for h in include_headers if h in headers}
                payload['headers'] = headers
            return json.dumps(payload)
        return str(payload)

    def process_response(self, request, response, spider):
        if not isinstance(response, TextResponse):
            return response

        puppeteer_request = request.meta.get('puppeteer_request')
        if puppeteer_request is None:
            return response

        if b'application/json' not in response.headers.get(b'Content-Type', b''):
            return response.replace(request=request)

        response_data = json.loads(response.text)
        response_cls = self._get_response_class(puppeteer_request.action)

        if response.status != 200:
            context_id = response_data.get('contextId')
            if context_id:
                self.used_contexts[id(spider)].add(context_id)
            return response

        return self._form_response(response_cls, response_data,
                                   puppeteer_request.url, request, puppeteer_request,
                                   spider)

    def _form_response(self, response_cls, response_data,
                       url, request, puppeteer_request,
                       spider):
        context_id = response_data.pop('contextId', puppeteer_request.context_id)
        page_id = response_data.pop('pageId', puppeteer_request.page_id)

        attributes = dict()
        for attr in response_cls.attributes:
            if attr in response_data:
                attributes[attr] = response_data.pop(attr)
        if response_data:
            attributes['data'] = response_data

        self.used_contexts[id(spider)].add(context_id)

        return response_cls(
            url=url,
            puppeteer_request=puppeteer_request,
            context_id=context_id,
            page_id=page_id,
            request=request,
            **attributes
        )

    @staticmethod
    def _get_response_class(request_action):
        if isinstance(request_action, (GoTo, GoForward, GoBack, Click, Scroll)):
            return PuppeteerHtmlResponse
        if isinstance(request_action, Screenshot):
            return PuppeteerScreenshotResponse
        return PuppeteerJsonResponse

    def close_used_contexts(self, spider):
        contexts = list(self.used_contexts[id(spider)])
        if contexts:
            request = Request(urljoin(self.service_base_url, '/close_context'),
                              method='POST',
                              headers=Headers({'Content-Type': 'application/json'}),
                              meta={"proxy": None},
                              body=json.dumps(contexts))
            return self.crawler.engine.downloader.fetch(request, None)


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

    def __init__(self,
                 recaptcha_solving: bool,
                 submit_selectors: dict):
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
            submit_selectors = crawler.settings.getdict(cls.SUBMIT_SELECTORS_SETTING, dict())
        except ValueError:
            submit_selectors = {'': crawler.settings.get(cls.SUBMIT_SELECTORS_SETTING, '')}
        except Exception as exception:
            raise ValueError(f"Wrong argument(s) inside {cls.SUBMIT_SELECTORS_SETTING}: {exception}")

        for key in submit_selectors.keys():
            submit_selector = submit_selectors[key]
            if isinstance(submit_selector, str):
                submit_selectors[key] = Click(selector=submit_selector)
            elif not isinstance(submit_selector, Click):
                raise ValueError("Submit selector must be str or Click,"
                                 f"but {type(submit_selector)} provided")
        return cls(recaptcha_solving, submit_selectors)

    def process_request(self, request, spider):
        if request.meta.get('dont_recaptcha', False):
            return None

        if isinstance(request, PuppeteerRequest):
            if request.close_page and not request.meta.get('_captcha_submission', False):
                request.close_page = False
                request.dont_filter = True
                self._page_closing.add(request)
                return request
        return None

    def process_response(self,
                         request, response,
                         spider):
        if not isinstance(response, PuppeteerResponse):  # We only work with PuppeteerResponses
            return response

        if request.meta.get('dont_recaptcha', False):  # Skip such responses
            return response

        if request.meta.pop('_captcha_submission', False):  # Submitted captcha
            return self.__gen_response(response)

        if request.meta.pop('_captcha_solving', False):
            # RECaptchaSolver was called by recaptcha middleware
            return self._submit_recaptcha(request, response, spider)

        if isinstance(response.puppeteer_request.action,
                      (Screenshot, Scroll, CustomJsAction, RecaptchaSolver)):
            # No recaptcha after this action
            return response

        # Any puppeteer response besides RecaptchaSolver's PuppeteerResponse
        return self._solve_recaptcha(response)

    def _solve_recaptcha(self, response):
        self._page_responses[response.page_id] = response  # Saving main response to return it later

        recaptcha_solver = RecaptchaSolver(solve_recaptcha=self.recaptcha_solving,
                                           close_on_empty=self.__is_closing(response, remove_request=False))
        return response.follow(recaptcha_solver,
                               meta={'_captcha_solving': True},
                               close_page=False)

    def _submit_recaptcha(self, request, response, spider):
        response_data = response.data
        if not response.puppeteer_request.action.solve_recaptcha:
            spider.log(message=f"Found {len(response_data['recaptcha_data']['captchas'])} captcha "
                               f"but did not solve due to argument",
                       level=logging.INFO)
            return self.__gen_response(response)
        # Click "submit button"?
        if response_data['recaptcha_data']['captchas'] and self.submit_selectors:
            # We need to click "submit button"
            for domain, submitting in self.submit_selectors.items():
                if domain in response.url:
                    if not submitting.selector:
                        return self.__gen_response(response)
                    return response.follow(action=submitting,
                                           callback=request.callback,
                                           errback=request.errback,
                                           close_page=self.__is_closing(response),
                                           meta={'_captcha_submission': True})
            raise IgnoreRequest("No submit selector found to click on the page but captcha found")
        return self.__gen_response(response)

    def __gen_response(self, response):
        main_response_data = dict()
        main_response_data['page_id'] = None if self.__is_closing(response) else response.puppeteer_request.page_id

        main_response = self._page_responses.pop(response.page_id)

        if isinstance(main_response, PuppeteerHtmlResponse):
            if isinstance(response.puppeteer_request.action, RecaptchaSolver):
                main_response_data['body'] = response.data['html']
            elif isinstance(response.puppeteer_request.action, Click):
                main_response_data['body'] = response.body

        return main_response.replace(**main_response_data)

    def __is_closing(self, response,
                     remove_request: bool = True) -> bool:
        main_request = self._page_responses[response.page_id].puppeteer_request
        close_page = main_request in self._page_closing
        if close_page and remove_request:
            self._page_closing.remove(main_request)
        return close_page
