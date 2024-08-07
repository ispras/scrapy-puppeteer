from scrapypuppeteer.response import (
    PuppeteerHtmlResponse,
    PuppeteerScreenshotResponse,
)
from scrapypuppeteer.request import ActionRequest, PuppeteerRequest, CloseContextRequest

import asyncio
from pyppeteer import launch
import syncer
import uuid
import base64
from scrapypuppeteer.browser_managers import BrowserManager


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

    def close_contexts(self, request: CloseContextRequest):
        for context_id in request.contexts:
            if context_id in self.contexts:
                syncer.sync(self.contexts[context_id].close())
                page_id = self.context_page_map.get(context_id)
                if page_id in self.pages:
                    del self.pages[page_id]

                del self.contexts[context_id]
                del self.context_page_map[context_id]

    def __del__(self):
        self.close_browser()


class LocalBrowserManager(BrowserManager):

    def __init__(self):
        self.context_manager = ContextManager()
        self.action_map = {
            "goto": self.goto,
            "click": self.click,
            "back": self.go_back,
            "forward": self.go_forward,
            "scroll": self.scroll,
            "screenshot": self.screenshot,
            "action": self.action,
            "recaptcha_solver": self.recaptcha_solver,
            "har": self.har
        }

    def process_request(self, request):
        
        if isinstance(request, PuppeteerRequest):
            endpoint = request.action.endpoint
            action_function = self.action_map.get(endpoint)
            if action_function:
                return action_function(request)
            
        if isinstance(request, CloseContextRequest):
            return self.close_contexts(request)
        
    def close_contexts(self, request: CloseContextRequest):
        self.context_manager.close_contexts(request)
    
    def close_used_contexts(self):
        self.context_manager.close_browser()

    def process_response(self, middleware, request, response, spider):
        return response
    
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

    def goto(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(request.context_id, request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_goto():
            url = request.action.payload()["url"]
            cookies = request.cookies
            navigation_options = request.action.navigation_options
            await page.goto(url, navigation_options)
            wait_options = request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            return PuppeteerHtmlResponse(url,
                                        request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)
        
        return syncer.sync(async_goto())

    def click(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(request.context_id, request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_click():
            selector = request.action.payload().get("selector")
            cookies = request.cookies
            click_options = request.action.click_options or {}
            navigation_options = request.action.navigation_options or {}
            options = merged = {**click_options, **navigation_options}
            await page.click(selector, options)
            wait_options = request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            return PuppeteerHtmlResponse(request.url,
                                        request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)
        
        return syncer.sync(async_click())

    def go_back(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(request.context_id, request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_go_back():
            cookies = request.cookies
            navigation_options = request.action.navigation_options
            await page.goBack(navigation_options)
            wait_options = request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            return PuppeteerHtmlResponse(request.url,
                                        request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

        return syncer.sync(async_go_back())


    def go_forward(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(request.context_id, request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_go_forward():
            cookies = request.cookies
            navigation_options = request.action.navigation_options
            await page.goForward(navigation_options)
            wait_options = request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            return PuppeteerHtmlResponse(request.url,
                                        request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

        return syncer.sync(async_go_forward())



    def screenshot(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(request.context_id, request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_screenshot():
            request_options = request.action.options or {}
            screenshot_options = {'encoding': 'binary'}
            screenshot_options.update(request_options)
            screenshot_bytes = await page.screenshot(screenshot_options)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            return PuppeteerScreenshotResponse(request.url,
                                        request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        screenshot = screenshot_base64)

        return syncer.sync(async_screenshot())
    

    def scroll(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(request.context_id, request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_scroll():
            cookies = request.cookies
            selector = request.action.payload().get("selector", None)

            if selector:
                script = f"""
                document.querySelector('{selector}').scrollIntoView();
                """
            else:
                script = """
                window.scrollBy(0, document.body.scrollHeight);
                """
            await page.evaluate(script)
            wait_options = request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            return PuppeteerHtmlResponse(request.url,
                                        request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

        return syncer.sync(async_scroll())
    

    def action(self, request: PuppeteerRequest):
        raise ValueError("CustomJsAction is not available in local mode")

    def recaptcha_solver(self, request: PuppeteerRequest):
        raise ValueError("RecaptchaSolver is not available in local mode")
    
    def har(self, request: PuppeteerRequest):
        raise ValueError("Har is not available in local mode")



