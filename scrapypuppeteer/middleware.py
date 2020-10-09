import json
from collections import defaultdict
from urllib.parse import urljoin, urlencode

from scrapy import Request, signals
from scrapy.crawler import Crawler
from scrapy.http import Headers, TextResponse

from scrapypuppeteer import PuppeteerRequest, PuppeteerHtmlResponse
from scrapypuppeteer.actions import CustomJsAction, Screenshot
from scrapypuppeteer.response import PuppeteerJsonResponse, PuppeteerScreenshotResponse


class PuppeteerServiceDownloaderMiddleware:
    """
    This downloader middleware converts PuppeteerRequest instances to
    Puppeteer service API requests and then converts its responses to
    PuppeteerResponse instances. Additionally it tracks all browser contexts
    that spider uses and performs cleanup request to service once spider
    is closed.

    Puppeteer service URL may be set via PUPPETEER_SERVICE_URL setting.
    """

    def __init__(self, crawler: Crawler, service_url: str):
        self.service_base_url = service_url
        self.crawler = crawler
        self.used_contexts = defaultdict(set)

    @classmethod
    def from_crawler(cls, crawler):
        service_url = crawler.settings.get('PUPPETEER_SERVICE_URL')
        if service_url is None:
            raise ValueError('Puppeteer service URL must be provided')
        middleware = cls(crawler, service_url)
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

    @staticmethod
    def _serialize_body(action, request):
        payload = action.payload()
        if action.content_type == 'application/json':
            if isinstance(payload, dict):
                # disallow null values in top-level request parameters
                payload = {k: v for k, v in payload.items() if v is not None}
            proxy = request.meta.get('proxy')
            if proxy:
                payload['proxy'] = proxy
            payload['headers'] = request.headers.to_unicode_dict()
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
        if 'html' in response_data and not isinstance(request_action, CustomJsAction):
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
