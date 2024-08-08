from scrapypuppeteer.response import (
    PuppeteerHtmlResponse,
    PuppeteerScreenshotResponse,
)
from scrapypuppeteer.request import ActionRequest, PuppeteerRequest

import asyncio
from pyppeteer import launch
import syncer
import uuid
import base64

from scrapypuppeteer import BrowserManager


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
            return self.process_puppeteer_request(request)
        
        return None

        
    def process_puppeteer_request(self, request):
        endpoint = request.action.endpoint
        action_function = self.action_map.get(endpoint)
        if action_function:
            return action_function(request)
        return None
    
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

    def goto(self, puppeteer_request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_goto():
            url = puppeteer_request.action.payload()["url"]
            cookies = puppeteer_request.cookies
            navigation_options = puppeteer_request.action.navigation_options
            await page.goto(url, navigation_options)
            wait_options = puppeteer_request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()

            puppeteer_html_response = PuppeteerHtmlResponse(url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

            return puppeteer_html_response
        return syncer.sync(async_goto())



    def click(self, puppeteer_request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_click():
            selector = puppeteer_request.action.payload().get("selector")
            cookies = puppeteer_request.cookies
            click_options = puppeteer_request.action.click_options or {}
            navigation_options = puppeteer_request.action.navigation_options or {}
            options = merged = {**click_options, **navigation_options}
            await page.click(selector, options)
            wait_options = puppeteer_request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            url = puppeteer_request.url

            puppeteer_html_response = PuppeteerHtmlResponse(url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)
            return puppeteer_html_response
        return syncer.sync(async_click())




    def go_back(self, puppeteer_request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_go_back():
            cookies = puppeteer_request.cookies
            navigation_options = puppeteer_request.action.navigation_options
            await page.goBack(navigation_options)
            wait_options = puppeteer_request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            url = puppeteer_request.url
            puppeteer_html_response = PuppeteerHtmlResponse(url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

            return puppeteer_html_response

        return syncer.sync(async_go_back())


    def go_forward(self, puppeteer_request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_go_forward():
            cookies = puppeteer_request.cookies
            navigation_options = puppeteer_request.action.navigation_options
            await page.goForward(navigation_options)
            wait_options = puppeteer_request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            url = puppeteer_request.url
            puppeteer_html_response = PuppeteerHtmlResponse(url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

            return puppeteer_html_response

        return syncer.sync(async_go_forward())



    def screenshot(self, puppeteer_request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_screenshot():
            request_options = puppeteer_request.action.options or {}
            screenshot_options = {'encoding': 'binary'}
            screenshot_options.update(request_options)
            screenshot_bytes = await page.screenshot(screenshot_options)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            url = puppeteer_request.url

            puppeteer_screenshot_response = PuppeteerScreenshotResponse(url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        screenshot = screenshot_base64)

            return puppeteer_screenshot_response

        return syncer.sync(async_screenshot())
    

    def scroll(self, puppeteer_request: PuppeteerRequest):
        context_id, page_id = syncer.sync(self.context_manager.check_context_and_page(puppeteer_request.context_id, puppeteer_request.page_id))
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_scroll():
            cookies = puppeteer_request.cookies
            selector = puppeteer_request.action.payload().get("selector", None)

            if selector:
                script = f"""
                document.querySelector('{selector}').scrollIntoView();
                """
            else:
                script = """
                window.scrollBy(0, document.body.scrollHeight);
                """

            await page.evaluate(script)
            wait_options = puppeteer_request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)

            response_html = await page.content()
            url = puppeteer_request.url
            puppeteer_html_response = PuppeteerHtmlResponse(url,
                                        puppeteer_request,
                                        context_id = context_id,
                                        page_id = page_id,
                                        html = response_html,
                                        cookies=cookies)

            return puppeteer_html_response

        return syncer.sync(async_scroll())
    

    def action(self, puppeteer_request: PuppeteerRequest):
        raise ValueError("CustomJsAction is not available in local mode")


    
    def recaptcha_solver(self, puppeteer_request: PuppeteerRequest):
        raise ValueError("RecaptchaSolver is not available in local mode")
    
    def har(self, puppeteer_request: PuppeteerRequest):
        raise ValueError("Har is not available in local mode")


    
    def close_used_contexts(self):
        self.context_manager.close_browser()

