import json
import logging
from collections import defaultdict
from typing import List, Union
from urllib.parse import urljoin, urlencode

from scrapy import Request, signals, Spider
from scrapy.crawler import Crawler
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Headers, TextResponse

from scrapypuppeteer import PuppeteerRequest, PuppeteerHtmlResponse, PuppeteerResponse
from scrapypuppeteer.actions import Screenshot, RecaptchaSolver, Click
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

        response_cls = self._get_response_class(puppeteer_request.action, response_data)
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
    def _get_response_class(request_action, response_data):
        if 'html' in response_data and 'recaptcha_data' not in response_data:
            return PuppeteerHtmlResponse
        if 'screenshot' in response_data and isinstance(request_action, Screenshot):
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
    It can sumit recaptcha if "submit button" is provided.
    It will not "submit" captcha if there is no submit-selector.

    You can provide "submit button" with settings.py inside your scrapy project.
    """

    RECAPTCHA_SOLVING_SETTING = "RECAPTCHA_SOLVING"
    SUBMIT_SELECTOR_SETTING = "SUBMIT_RECAPTCHA_SELECTOR"
    NO_SUBMIT_SETTING = "NO_SUBMIT_SELECTOR"

    def __init__(self,
                 recaptcha_solving: bool,
                 submit_selectors: list[str],
                 no_submit_selector: bool):
        self.submit_selectors = set(submit_selectors)
        self.recaptcha_solving = recaptcha_solving
        self.no_submit_selector = no_submit_selector
        self._context_response = dict()

    @classmethod
    def from_crawler(cls, crawler: Crawler):

        recaptcha_solving = crawler.settings.get(cls.RECAPTCHA_SOLVING_SETTING, True)
        submit_selectors = crawler.settings.get(cls.SUBMIT_SELECTOR_SETTING)
        no_submit_selector = crawler.settings.get(cls.NO_SUBMIT_SETTING)
        if recaptcha_solving and not submit_selectors and no_submit_selector:
            raise ValueError('No submit selectors provided but automatic solving is enabled')
        return cls(recaptcha_solving, submit_selectors, no_submit_selector)

    @staticmethod
    def process_request(request: Request, spider: Spider):
        # We don't modify any request, we only work with responses
        return None

    def process_response(self,
                         request, response,
                         spider: Spider):
        if isinstance(response, PuppeteerJsonResponse) and \
                isinstance(response.puppeteer_request.action, Click):
            if response.puppeteer_request.action.selector in self.submit_selectors:
                return self._context_response.pop(response.context_id, response)

        if isinstance(response, PuppeteerJsonResponse) and \
                isinstance(response.puppeteer_request.action, RecaptchaSolver):
            # RECaptchaSolver was called by recaptcha middleware
            response_data = response.data['recaptcha_data']
            if not response.puppeteer_request.action.solve_recaptcha:
                spider.log(message=f"Found {len(response_data['captcha'])} captcha but did not solve due to argument",
                           level=logging.WARNING)
                return self._context_response.pop(response.context_id, response)
            # We need to click "submit button"
            for submit_selector in self.submit_selectors:
                if submit_selector in response.body:
                    submit_click = Click(submit_selector)
                    return PuppeteerRequest(action=submit_click,
                                            close_page=response.puppeteer_request.close_page)
            raise IgnoreRequest

        # We only work with PuppeteerResponses
        # What if we did not prove 2catpcha token?:
        if isinstance(response, PuppeteerResponse):  # Any puppeteer response besides JsonResponse
            # Seems to be done!
            if response.puppeteer_request.close_page:
                return response
            # Here we need to find recaptcha and solve it
            recaptcha_solver = RecaptchaSolver(solve_recaptcha=self.recaptcha_solving)
            # after that we need to save response's answer, so we could return it later
            if isinstance(response, PuppeteerJsonResponse):
                self._context_response[response.context_id] = response.copy()
            return response.follow(recaptcha_solver, close_page=False)
        return response
