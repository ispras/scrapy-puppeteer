import json
import logging
from collections import defaultdict
from urllib.parse import urlencode, urljoin

from scrapy.exceptions import DontCloseSpider
from scrapy.http import Headers, Response, TextResponse
from scrapy.utils.log import failure_to_exc_info
from twisted.python.failure import Failure

from scrapypuppeteer.actions import (
    CaptchaSolver,
    Click,
    Compose,
    FillForm,
    GoBack,
    GoForward,
    GoTo,
    Har,
    RecaptchaSolver,
    Screenshot,
    Scroll,
)
from scrapypuppeteer.browser_managers import BrowserManager
from scrapypuppeteer.request import ActionRequest, CloseContextRequest, PuppeteerRequest
from scrapypuppeteer.response import (
    PuppeteerCaptchaSolverResponse,
    PuppeteerHarResponse,
    PuppeteerHtmlResponse,
    PuppeteerJsonResponse,
    PuppeteerRecaptchaSolverResponse,
    PuppeteerScreenshotResponse,
)


class ServiceBrowserManager(BrowserManager):
    def __init__(self, service_base_url, include_meta, include_headers, crawler):
        self.service_base_url = service_base_url
        self.include_meta = include_meta
        self.include_headers = include_headers
        self.used_contexts = defaultdict(set)
        self.service_logger = logging.getLogger(__name__)
        self.crawler = crawler

        if self.service_base_url is None:
            raise ValueError("Puppeteer service URL must be provided")

    def process_request(self, request):
        if isinstance(request, CloseContextRequest):
            return self.process_close_context_request(request)

        if isinstance(request, PuppeteerRequest):
            return self.process_puppeteer_request(request)

    def process_close_context_request(self, request: CloseContextRequest):
        if not request.is_valid_url:
            return request.replace(
                url=urljoin(self.service_base_url, "/close_context"),
            )

    def process_puppeteer_request(self, request: PuppeteerRequest):
        action = request.action
        service_url = urljoin(self.service_base_url, action.endpoint)
        service_params = self._encode_service_params(request)
        if service_params:
            service_url += "?" + service_params
        meta = {
            "puppeteer_request": request,
            "dont_obey_robotstxt": True,
            "proxy": None,
        }
        if self.include_meta:
            meta = {**request.meta, **meta}
        action_request = ActionRequest(
            url=service_url,
            action=action,
            method="POST",
            headers=Headers({"Content-Type": action.content_type}),
            body=self._serialize_body(action, request),
            dont_filter=True,
            cookies=request.cookies,
            priority=request.priority,
            callback=request.callback,
            cb_kwargs=request.cb_kwargs,
            errback=request.errback,
            meta=meta,
        )
        return action_request

    @staticmethod
    def _encode_service_params(request):
        service_params = {}
        if request.context_id is not None:
            service_params["contextId"] = request.context_id
        if request.page_id is not None:
            service_params["pageId"] = request.page_id
        if request.close_page:
            service_params["closePage"] = 1
        return urlencode(service_params)

    def _serialize_body(self, action, request):
        payload = action.payload()
        if action.content_type == "application/json":
            payload = self.__clean_payload(payload)
            proxy = request.meta.get("proxy")
            if proxy:
                payload["proxy"] = proxy
            include_headers = (
                self.include_headers
                if request.include_headers is None
                else request.include_headers
            )
            if include_headers:
                headers = request.headers.to_unicode_dict()
                if isinstance(include_headers, list):
                    headers = {
                        h.lower(): headers[h] for h in include_headers if h in headers
                    }
                payload["headers"] = headers
            return json.dumps(payload)
        return str(payload)

    def __clean_payload(self, payload):
        """
        disallow null values in request parameters
        """
        if isinstance(payload, dict):
            payload = {
                k: self.__clean_payload(v) for k, v in payload.items() if v is not None
            }
        elif isinstance(payload, list):
            payload = [self.__clean_payload(v) for v in payload if v is not None]
        return payload

    def close_used_contexts(self, spider):
        contexts = list(self.used_contexts.pop(id(spider), set()))
        if contexts:
            request = CloseContextRequest(
                contexts,
                meta={"proxy": None},
            )

            def handle_close_contexts_result(result):
                if isinstance(result, Response):
                    if result.status == 200:
                        self.service_logger.debug(
                            f"Successfully closed {len(request.contexts)} "
                            f"contexts with request {result.request}"
                        )
                    else:
                        self.service_logger.warning(
                            f"Could not close contexts: {result.text}"
                        )
                elif isinstance(result, Failure):
                    self.service_logger.warning(
                        f"Could not close contexts: {result.value}",
                        exc_info=failure_to_exc_info(result),
                    )

            dfd = self.crawler.engine.download(request)
            dfd.addBoth(handle_close_contexts_result)

            raise DontCloseSpider()

    def process_response(self, middleware, request, response, spider):
        if not isinstance(response, TextResponse):
            return response

        puppeteer_request = request.meta.get("puppeteer_request")
        if puppeteer_request is None:
            return response

        if b"application/json" not in response.headers.get(b"Content-Type", b""):
            return response.replace(request=request)

        response_data = json.loads(response.text)
        if response.status != 200:
            reason = response_data.pop("error", f"undefined, status {response.status}")
            middleware.service_logger.warning(
                f"Request {request} is not succeeded. Reason: {reason}"
            )
            context_id = response_data.get("contextId")
            if context_id:
                self.used_contexts[id(spider)].add(context_id)
            return response

        response_cls = self._get_response_class(puppeteer_request.action)

        return self._form_response(
            response_cls,
            response_data,
            puppeteer_request.url,
            request,
            puppeteer_request,
            spider,
        )

    def _form_response(
        self,
        response_cls,
        response_data,
        url,
        request,
        puppeteer_request,
        spider,
    ):
        context_id = response_data.pop("contextId", puppeteer_request.context_id)
        page_id = response_data.pop("pageId", puppeteer_request.page_id)
        self.used_contexts[id(spider)].add(context_id)

        return response_cls(
            url=url,
            puppeteer_request=puppeteer_request,
            context_id=context_id,
            page_id=page_id,
            request=request,
            **response_data,
        )

    def _get_response_class(self, request_action):
        if isinstance(
            request_action, (GoTo, GoForward, GoBack, Click, Scroll, FillForm)
        ):
            return PuppeteerHtmlResponse
        if isinstance(request_action, CaptchaSolver):
            return PuppeteerCaptchaSolverResponse
        if isinstance(request_action, Screenshot):
            return PuppeteerScreenshotResponse
        if isinstance(request_action, Har):
            return PuppeteerHarResponse
        if isinstance(request_action, RecaptchaSolver):
            return PuppeteerRecaptchaSolverResponse
        if isinstance(request_action, Compose):
            # Response class is a last action's response class
            return self._get_response_class(request_action.actions[-1])
        return PuppeteerJsonResponse
