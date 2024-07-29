import json
import logging
from collections import defaultdict
from typing import List, Union
from urllib.parse import urlencode, urljoin
from abc import ABC, abstractmethod

from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.exceptions import IgnoreRequest, NotConfigured, DontCloseSpider
from scrapy.http import Headers, TextResponse, Response
from scrapy.utils.log import failure_to_exc_info
from twisted.python.failure import Failure
import time

from scrapypuppeteer.actions import (
    Click,
    GoBack,
    GoForward,
    GoTo,
    RecaptchaSolver,
    Screenshot,
    Scroll,
    CustomJsAction,
)
from scrapypuppeteer.response import (
    PuppeteerResponse,
    PuppeteerHtmlResponse,
    PuppeteerScreenshotResponse,
    PuppeteerRecaptchaSolverResponse,
    PuppeteerJsonResponse,
)
from scrapypuppeteer.request import ActionRequest, PuppeteerRequest, CloseContextRequest



import asyncio
from pyppeteer import launch
import syncer
import uuid
import base64


class ContextManager:

    def __init__(self):
        self.browser = syncer.sync(launch())
        self.contexts = {}
        self.pages = {}
        self.context_page_map = {}


    async def check_context_and_page(self, context_id, page_id):
        if not context_id or not page_id:
            context_id, page_id = await self.open_new_page()
        return context_id, page_id

    async def open_new_page(self):
        context_id = uuid.uuid4().hex.upper()
        page_id = uuid.uuid4().hex.upper()

        self.contexts[context_id] = await self.browser.createIncognitoBrowserContext()
        self.pages[page_id] = await self.contexts[context_id].newPage()
        self.context_page_map[context_id] = page_id

        return context_id, page_id

    def get_page_by_id(self, context_id, page_id):
        return self.pages[page_id]



    def close_browser(self):
        if self.browser:
            syncer.sync(self.browser.close())

    def __del__(self):
        self.close_browser()


class RequestHandler:
    def __init__(self):
        self.context_manager = ContextManager()

    def process_puppeteer_request(self, action_request):
        endpoint = action_request.action.endpoint
        action_map = {
            "goto": self.goto,
            "click": self.click,
            "back": self.go_back,
            "forward": self.go_forward,
            "scroll": self.scroll,
            "screenshot": self.screenshot,
            "action": self.action,
            "recaptcha_solver": self.recaptcha_solver
        }

        action_function = action_map.get(endpoint)
        if action_function:
            return action_function(action_request)

        return None
    
    async def wait_with_options(self, page, wait_options):
        timeout = wait_options.get("selectorOrTimeout", 1000)
        visible = wait_options.get("visible", False)
        hidden = wait_options.get("hidden", False)

        if isinstance(timeout, (int, float)):
            await asyncio.sleep(timeout / 1000)
        else:
            await page.waitFor(selector=timeout, options={
                'visible': visible,
                'hidden': hidden,
                'timeout': 30000
            })

    def goto(self, action_request: ActionRequest):
        puppeteer_request = action_request.meta.get("puppeteer_request")
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_goto():
            url = action_request.action.payload()["url"]
            service_url = action_request.url
            cookies = action_request.cookies
            navigation_options = action_request.action.navigation_options
            await page.goto(url, navigation_options)
            wait_options = action_request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()

            puppeteer_html_response = PuppeteerHtmlResponse(service_url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

            return puppeteer_html_response
        return syncer.sync(async_goto())

    def click(self, action_request: ActionRequest):
        puppeteer_request = action_request.meta.get("puppeteer_request")
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_click():
            selector = action_request.action.payload().get("selector")
            cookies = action_request.cookies
            click_options = action_request.action.click_options or {}
            navigation_options = action_request.action.navigation_options or {}
            options = merged = {**click_options, **navigation_options}
            await page.click(selector, options)
            wait_options = action_request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            service_url = action_request.url

            puppeteer_html_response = PuppeteerHtmlResponse(service_url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)
            return puppeteer_html_response
        return syncer.sync(async_click())




    def go_back(self, action_request: ActionRequest):
        puppeteer_request = action_request.meta.get("puppeteer_request")
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_go_back():
            cookies = action_request.cookies
            navigation_options = action_request.action.navigation_options
            await page.goBack(navigation_options)
            wait_options = action_request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            service_url = action_request.url
            puppeteer_html_response = PuppeteerHtmlResponse(service_url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

            return puppeteer_html_response

        return syncer.sync(async_go_back())


    def go_forward(self, action_request: ActionRequest):
        puppeteer_request = action_request.meta.get("puppeteer_request")
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_go_forward():
            cookies = action_request.cookies
            navigation_options = action_request.action.navigation_options
            await page.goForward(navigation_options)
            wait_options = action_request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            service_url = action_request.url
            puppeteer_html_response = PuppeteerHtmlResponse(service_url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

            return puppeteer_html_response

        return syncer.sync(async_go_forward())



    def screenshot(self, action_request: ActionRequest):
        puppeteer_request = action_request.meta.get("puppeteer_request")
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_screenshot():
            request_options = action_request.action.options or {}
            screenshot_options = {'encoding': 'binary'}
            screenshot_options.update(request_options)
            screenshot_bytes = await page.screenshot(screenshot_options)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            service_url = action_request.url

            puppeteer_screenshot_response = PuppeteerScreenshotResponse(service_url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        screenshot = screenshot_base64)

            return puppeteer_screenshot_response

        return syncer.sync(async_screenshot())
    




    def scroll(self, action_request: ActionRequest):
        puppeteer_request = action_request.meta.get("puppeteer_request")
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_scroll():
            cookies = action_request.cookies
            selector = action_request.action.payload().get("selector", None)

            if selector:
                script = f"""
                document.querySelector('{selector}').scrollIntoView();
                """
            else:
                script = """
                window.scrollBy(0, document.body.scrollHeight);
                """

            await page.evaluate(script)
            wait_options = action_request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)

            response_html = await page.content()
            service_url = action_request.url
            puppeteer_html_response = PuppeteerHtmlResponse(service_url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

            return puppeteer_html_response

        return syncer.sync(async_scroll())
    

    def action(self, action_request: ActionRequest):
        raise ValueError("CustomJsAction is not available in local mode")


    
    def recaptcha_solver(self, action_request: ActionRequest):
        raise ValueError("RecaptchaSolver is not available in local mode")
    




class BrowserManager(ABC):
    @abstractmethod
    def process_request(self, request, spider):
        pass
    
    @abstractmethod
    def close_used_contexts(self):
        pass


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
                middleware.used_contexts[id(spider)].add(context_id)
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
        self, response_cls, response_data, url, request, puppeteer_request, spider
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

    @staticmethod
    def _get_response_class(request_action):
        if isinstance(request_action, (GoTo, GoForward, GoBack, Click, Scroll)):
            return PuppeteerHtmlResponse
        if isinstance(request_action, Screenshot):
            return PuppeteerScreenshotResponse
        if isinstance(request_action, RecaptchaSolver):
            return PuppeteerRecaptchaSolverResponse
        return PuppeteerJsonResponse


class LocalBrowserManager(BrowserManager):
    def __init__(self):
        self.request_handler = RequestHandler()

    def process_request(self, request):
        action_request = ActionRequest(
            url='http://_running_local_',
            action=request.action,
            cookies=request.cookies,
            meta={"puppeteer_request": request}
        )

 
        return self.request_handler.process_puppeteer_request(action_request)

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
    
    def close_used_contexts(self):
        self.request_handler.context_manager.close_browser()


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
        action_request =  ActionRequest(
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
            if isinstance(payload, dict):
                # disallow null values in top-level request parameters
                payload = {k: v for k, v in payload.items() if v is not None}
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