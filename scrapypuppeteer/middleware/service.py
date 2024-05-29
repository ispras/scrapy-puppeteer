import json

from collections import defaultdict
from typing import List, Union
from urllib.parse import urlencode, urljoin
from http import HTTPStatus

from scrapy import Request, signals
from scrapy.crawler import Crawler
from scrapy.http import Headers, TextResponse

from scrapypuppeteer.actions import Click, GoBack, GoForward, GoTo, Screenshot, Scroll
from scrapypuppeteer.response import PuppeteerHtmlResponse, PuppeteerScreenshotResponse, PuppeteerJsonResponse
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
    May be overridden per request.
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

        if response.status != HTTPStatus.OK:
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
