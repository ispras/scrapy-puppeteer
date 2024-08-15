from scrapypuppeteer.response import (
    PuppeteerHtmlResponse,
    PuppeteerScreenshotResponse,
)
from scrapypuppeteer.request import ActionRequest, PuppeteerRequest, CloseContextRequest

import asyncio
from playwright.async_api import async_playwright
import syncer
import uuid
import base64
from scrapypuppeteer.browser_managers import BrowserManager


class ContextManager:
    def __init__(self):
        self.browser = syncer.sync(self.launch_browser())
        self.contexts = {}
        self.pages = {}
        self.context_page_map = {}

    async def launch_browser(self):
        playwright = await async_playwright().start()
        return await playwright.chromium.launch(headless=False)

    async def check_context_and_page(self, context_id, page_id):
        if not context_id or not page_id:
            context_id, page_id = await self.open_new_page()
        return context_id, page_id

    async def open_new_page(self):
        print("Playwright processing - New Page")
        context_id = uuid.uuid4().hex.upper()
        page_id = uuid.uuid4().hex.upper()

        self.contexts[context_id] = await self.browser.new_context()
        self.pages[page_id] = await self.contexts[context_id].new_page()
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


class PlaywrightBrowserManager(BrowserManager):
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
            "har": self.har,
            "fill_form": self.fill_form,
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

    def map_navigation_options_to_target(self, navigation_options):
        if not navigation_options:
            return {}
        event_map = {
            "load": "load",
            "domcontentloaded": "domcontentloaded",
            "networkidle0": "networkidle",
            "networkidle2": "networkidle",
        }
        mapped_navigation_options = {}
        if "timeout" in navigation_options:
            mapped_navigation_options["timeout"] = navigation_options["timeout"]
        waitUntil = navigation_options.get("waitUntil")
        if waitUntil:
            first_event = waitUntil[0] if isinstance(waitUntil, list) else waitUntil

            if first_event in event_map:
                mapped_navigation_options["wait_until"] = event_map[first_event]
            else:
                raise ValueError(f"Invalid waitUntil value: {first_event}")

        return mapped_navigation_options

    def map_click_options(self, click_options):
        if not click_options:
            return {}
        maped_click_options = {
            "delay": click_options.get("delay", 0.0),
            "button": click_options.get("button", "left"),
            "click_count": click_options.get("clickCount", 1),
        }
        return maped_click_options

    async def wait_with_options(self, page, wait_options):
        timeout = wait_options.get("selectorOrTimeout", 1000)
        visible = wait_options.get("visible", False)
        hidden = wait_options.get("hidden", False)

        if isinstance(timeout, (int, float)):
            await asyncio.sleep(timeout / 1000)
        else:
            await page.wait_for_selector(
                selector=timeout, state="visible" if visible else "hidden"
            )

    def goto(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(
            self.context_manager.check_context_and_page(
                request.context_id, request.page_id
            )
        )
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_goto():
            url = request.action.payload()["url"]
            cookies = request.cookies
            navigation_options = self.map_navigation_options_to_target(
                request.action.navigation_options
            )
            await page.goto(url, **navigation_options)
            wait_options = request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            return PuppeteerHtmlResponse(
                url,
                request,
                context_id=context_id,
                page_id=page_id,
                html=response_html,
                cookies=cookies,
            )

        return syncer.sync(async_goto())

    def click(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(
            self.context_manager.check_context_and_page(
                request.context_id, request.page_id
            )
        )
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_click():
            selector = request.action.payload().get("selector")
            cookies = request.cookies
            click_options = self.map_click_options(request.action.click_options)
            await page.click(selector, **click_options)
            wait_options = request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            return PuppeteerHtmlResponse(
                request.url,
                request,
                context_id=context_id,
                page_id=page_id,
                html=response_html,
                cookies=cookies,
            )

        return syncer.sync(async_click())

    def go_back(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(
            self.context_manager.check_context_and_page(
                request.context_id, request.page_id
            )
        )
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_go_back():
            cookies = request.cookies
            navigation_options = self.map_navigation_options_to_target(
                request.action.navigation_options
            )
            await page.go_back(**navigation_options)
            wait_options = request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            return PuppeteerHtmlResponse(
                request.url,
                request,
                context_id=context_id,
                page_id=page_id,
                html=response_html,
                cookies=cookies,
            )

        return syncer.sync(async_go_back())

    def go_forward(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(
            self.context_manager.check_context_and_page(
                request.context_id, request.page_id
            )
        )
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_go_forward():
            cookies = request.cookies
            navigation_options = self.map_navigation_options_to_target(
                request.action.navigation_options
            )
            await page.go_forward(**navigation_options)
            wait_options = request.action.payload().get("waitOptions", {}) or {}
            await self.wait_with_options(page, wait_options)
            response_html = await page.content()
            return PuppeteerHtmlResponse(
                request.url,
                request,
                context_id=context_id,
                page_id=page_id,
                html=response_html,
                cookies=cookies,
            )

        return syncer.sync(async_go_forward())

    def screenshot(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(
            self.context_manager.check_context_and_page(
                request.context_id, request.page_id
            )
        )
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_screenshot():
            request_options = request.action.options or {}

            screenshot_bytes = await page.screenshot(**request_options)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return PuppeteerScreenshotResponse(
                request.url,
                request,
                context_id=context_id,
                page_id=page_id,
                screenshot=screenshot_base64,
            )

        return syncer.sync(async_screenshot())

    def scroll(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(
            self.context_manager.check_context_and_page(
                request.context_id, request.page_id
            )
        )
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
            return PuppeteerHtmlResponse(
                request.url,
                request,
                context_id=context_id,
                page_id=page_id,
                html=response_html,
                cookies=cookies,
            )

        return syncer.sync(async_scroll())

    def fill_form(self, request: PuppeteerRequest):
        context_id, page_id = syncer.sync(
            self.context_manager.check_context_and_page(
                request.context_id, request.page_id
            )
        )
        page = self.context_manager.get_page_by_id(context_id, page_id)

        async def async_fill_form():
            input_mapping = request.action.payload().get("inputMapping")
            submit_button = request.action.payload().get("submitButton", None)
            cookies = request.cookies

            for selector, params in input_mapping.items():
                text = params.get("value", "no value was provided")
                delay = params.get("delay", 0)
                await page.type(selector, text=text, delay=delay)

            if submit_button:
                await page.click(submit_button)

            response_html = await page.content()
            return PuppeteerHtmlResponse(
                request.url,
                request,
                context_id=context_id,
                page_id=page_id,
                html=response_html,
                cookies=cookies,
            )

        return syncer.sync(async_fill_form())

    def action(self, request: PuppeteerRequest):
        raise ValueError("CustomJsAction is not available in local mode")

    def recaptcha_solver(self, request: PuppeteerRequest):
        raise ValueError("RecaptchaSolver is not available in local mode")

    def har(self, request: PuppeteerRequest):
        raise ValueError("Har is not available in local mode")
