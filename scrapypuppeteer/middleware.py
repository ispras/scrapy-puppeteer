import json
import logging
from collections import defaultdict
from typing import List, Union
from urllib.parse import urlencode, urljoin

from scrapy import Request, signals
from scrapy.crawler import Crawler
from scrapy.exceptions import IgnoreRequest, NotConfigured
from scrapy.http import Headers, TextResponse

from scrapypuppeteer import PuppeteerHtmlResponse, PuppeteerRequest, PuppeteerResponse
from scrapypuppeteer.actions import Click, GoBack, GoForward, GoTo, RecaptchaSolver, Screenshot, Scroll
from scrapypuppeteer.response import PuppeteerJsonResponse, PuppeteerScreenshotResponse


class PuppeteerServiceDownloaderMiddleware:
    """
    This downloader middleware converts PuppeteerRequest instances to
    Puppeteer service API requests and then converts its responses to
    PuppeteerResponse instances. Additionally, it tracks all browser contexts
    that spider uses and performs cleanup request to service once spider
    is closed.

    Settings:

    PUPPETEER_SERVICE_URL (str)
    Service URL, e.g. 'http://localhost:3000'

    PUPPETEER_INCLUDE_HEADERS (bool|list[str])
    Determines which request headers will be sent to remote site by puppeteer service.
    Either True (all headers), False (no headers) or list of header names.
    May be overriden per request.
    By default, only cookies are sent.
    """

    SERVICE_URL_SETTING = 'PUPPETEER_SERVICE_URL'
    INCLUDE_HEADERS_SETTING = 'PUPPETEER_INCLUDE_HEADERS'
    DEFAULT_INCLUDE_HEADERS = ['Cookie']  # TODO send them separately

    def __init__(self,
                 crawler: Crawler,
                 service_url: str,
                 include_headers: Union[bool, List[str]]):
        self.service_base_url = service_url
        self.include_headers = include_headers
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
        middleware = cls(crawler, service_url, include_headers)
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

        return Request(
            url=service_url,
            method='POST',
            headers=Headers({'Content-Type': action.content_type}),
            body=self._serialize_body(action, request),
            dont_filter=True,
            cookies=request.cookies,
            priority=request.priority,
            callback=request.callback,
            cb_kwargs=request.cb_kwargs,
            errback=request.errback,
            meta={
                'puppeteer_request': request,
                'dont_obey_robotstxt': True,
                'proxy': None
            }
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
            return response

        response_data = json.loads(response.text)
        context_id = response_data.pop('contextId', None)
        page_id = response_data.pop('pageId', None)

        response_cls = self._get_response_class(puppeteer_request.action)
        response = response_cls(
            url=puppeteer_request.url,
            puppeteer_request=puppeteer_request,
            context_id=context_id,
            page_id=page_id,
            **response_data
        )

        self.used_contexts[id(spider)].add(context_id)

        return response

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
    If there is no captcha on the page then this middleware will do nothing on
    the page, so your 2captcha balance will remain the same.
    It can submit recaptcha if "submit button" is provided.
    It will not "submit" captcha if there is no submit-selector.

    Settings:

    RECAPTCHA_ACTIVATION: bool = True - activates or not the middleware (if not - raises NotConfigured)
    RECAPTCHA_SOLVING: bool = True - whether solve captcha automatically or not
    RECAPTCHA_SUBMIT_SELECTOR: str | dict = {} - dictionary consisting of domains and
        these domains' submit selectors, e.g.
            'www.google.com/recaptcha/api2/demo': '#recaptcha-demo-submit'
        it could be also squeezed to
            'ecaptcha/api2/de': '#recaptcha-demo-submit'
        In general - unique identifying string which is contained in web-page url
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
        return cls(recaptcha_solving, submit_selectors)

    @staticmethod
    def process_request(request, spider):
        # We don't modify any request, we only work with responses
        return None

    def process_response(self,
                         request, response,
                         spider):
        if not isinstance(response, PuppeteerResponse):  # We only work with PuppeteerResponses
            return response

        if response.puppeteer_request.close_page:  # No need in solving captcha right before closing the page
            return response

        if request.meta.pop('_captcha_submission', False):  # Submitted captcha
            return self._gen_response(response)

        if isinstance(response.puppeteer_request.action, RecaptchaSolver):
            # RECaptchaSolver was called by recaptcha middleware
            return self._submit_recaptcha(request, response, spider)

        # Any puppeteer response besides RecaptchaSolver's PuppeteerResponse
        return self._solve_recaptcha(request, response)

    def _solve_recaptcha(self, request, response):
        recaptcha_solver = RecaptchaSolver(solve_recaptcha=self.recaptcha_solving)
        self._page_responses[response.page_id] = response  # Saving main response to return it later
        return response.follow(recaptcha_solver,
                               callback=request.callback,
                               errback=request.errback,
                               close_page=False)

    def _submit_recaptcha(self, request, response, spider):
        response_data = response.data
        if not response.puppeteer_request.action.solve_recaptcha:
            spider.log(message=f"Found {len(response_data['recaptcha_data']['captchas'])} captcha "
                               f"but did not solve due to argument",
                       level=logging.INFO)
            return self._gen_response(response)
        # Click "submit button"?
        if response_data['recaptcha_data']['captchas'] and self.submit_selectors:
            # We need to click "submit button"
            for domain, submit_selector in self.submit_selectors.items():
                if domain in response.url:
                    if not submit_selector:
                        return self._gen_response(response)
                    submit_click = Click(submit_selector)
                    return response.follow(action=submit_click,
                                           callback=request.callback,
                                           errback=request.errback,
                                           close_page=False,
                                           meta={'_captcha_submission': True})
            raise IgnoreRequest("No submit selector found to click on the page but captcha found")
        return self._gen_response(response)

    def _gen_response(self, response):
        main_response = self._page_responses.pop(response.page_id)

        if not isinstance(main_response, PuppeteerHtmlResponse):
            return main_response

        puppeteer_request = main_response.puppeteer_request
        context_id = main_response.context_id
        page_id = main_response.page_id
        main_response_data = dict()
        if isinstance(response.puppeteer_request.action, Click):
            main_response_data['html'] = response.body
        else:
            main_response_data['html'] = response.data['html']
        main_response_data['cookies'] = main_response.cookies
        main_response_data['headers'] = main_response.headers

        return PuppeteerHtmlResponse(
            url=puppeteer_request.url,
            puppeteer_request=puppeteer_request,
            context_id=context_id,
            page_id=page_id,
            **main_response_data
        )
