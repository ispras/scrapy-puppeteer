import asyncio
import base64
from json import dumps
from typing import Any, Awaitable, Callable, Dict, Union

from playwright.async_api import Page, async_playwright
from scrapy.http import TextResponse

from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.browser_managers import BrowserManager
from scrapypuppeteer.request import ActionRequest, CloseContextRequest
from scrapypuppeteer.browser_managers import ContextManager


class PlaywrightContextManager(ContextManager):
    @classmethod
    async def async_init(cls):
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        return cls(browser)

    @staticmethod
    async def _create_context(browser):
        return await browser.new_context()

    @staticmethod
    async def _create_page(context):
        return await context.new_page()


class PlaywrightBrowserManager(BrowserManager):
    def __init__(self):
        self.context_manager: Union[PlaywrightContextManager, None] = (
            None  # Will be initialized later
        )
        self.action_map: Dict[
            str, Callable[[Page, ActionRequest], Awaitable[Dict[str, Any]]]
        ] = {
            "goto": self.goto,
            "click": self.click,
            "compose": self.compose,
            "back": self.go_back,
            "forward": self.go_forward,
            "scroll": self.scroll,
            "screenshot": self.screenshot,
            "action": self.action,
            "recaptcha_solver": self.recaptcha_solver,
            "har": self.har,
            "fill_form": self.fill_form,
        }

    def _download_request(self, request, spider):
        if isinstance(request, ActionRequest):
            return self.__perform_action(request)
        if isinstance(request, CloseContextRequest):
            return self.close_contexts(request)

    async def _start_browser_manager(self) -> None:
        self.context_manager = await PlaywrightContextManager.async_init()

    async def _stop_browser_manager(self) -> None:
        if self.context_manager:
            await self.context_manager.close_browser()

    async def __perform_action(self, request: ActionRequest):
        pptr_request: PuppeteerRequest = request.meta["puppeteer_request"]
        endpoint = request.action.endpoint
        action_function = self.action_map.get(endpoint)
        if action_function:
            context_id, page_id = await self.context_manager.check_context_and_page(
                pptr_request.context_id, pptr_request.page_id
            )
            page = self.context_manager.get_page_by_id(context_id, page_id)

            try:
                response_data = await action_function(page, request)
            except Exception as e:
                return TextResponse(
                    request.url,
                    headers={"Content-Type": "application/json"},
                    body=dumps(
                        {
                            "error": str(e),
                            "contextId": context_id,
                            "pageId": page_id,
                        }
                    ),
                    status=500,
                    encoding="utf-8",
                )

            response_data["contextId"] = context_id
            response_data["pageId"] = page_id
            return TextResponse(
                request.url,
                headers={"Content-Type": "application/json"},
                body=dumps(response_data),
                encoding="utf-8",
            )
        raise ValueError(f"No such action: {endpoint}")

    async def close_contexts(self, request: CloseContextRequest) -> TextResponse:
        await self.context_manager.close_contexts(request)
        return TextResponse(
            request.url,
            encoding="utf-8",
            status=200,
            headers={},
            body=b"Successfully closed context",
        )

    async def close_used_contexts(self):
        await self.context_manager.close_browser()

    def map_navigation_options(self, navigation_options):
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
            if isinstance(waitUntil, list):
                event_hierarchy = [
                    "load",
                    "domcontentloaded",
                    "networkidle2",
                    "networkidle0",
                ]
                strictest_event = max(
                    waitUntil, key=lambda event: event_hierarchy.index(event)
                )
            elif isinstance(waitUntil, str):
                strictest_event = waitUntil
            else:
                raise TypeError(
                    f"waitUntil should be a list or a string, got {type(waitUntil)}"
                )

            if strictest_event in event_map:
                mapped_navigation_options["wait_until"] = event_map[strictest_event]

        return mapped_navigation_options

    def map_click_options(self, click_options):
        if not click_options:
            return {}
        mapped_click_options = {
            "delay": click_options.get("delay", 0.0),
            "button": click_options.get("button", "left"),
            "click_count": click_options.get("clickCount", 1),
        }
        return mapped_click_options

    def map_screenshot_options(self, screenshot_options):
        if not screenshot_options:
            return {}
        mapped_screenshot_options = {
            "type": screenshot_options.get("type", "png"),
            "quality": screenshot_options.get("quality", 100),
            "full_page": screenshot_options.get("fullPage", False),
            "clip": screenshot_options.get("clip"),
            "omit_background": screenshot_options.get("omitBackground"),
        }
        return mapped_screenshot_options

    async def wait_with_options(self, page, wait_options):
        selector = wait_options.get("selector")
        xpath = wait_options.get("xpath")
        timeout = wait_options.get("timeout", None)
        options = wait_options.get("options", {})

        selector_or_timeout = wait_options.get("selectorOrTimeout")
        if selector_or_timeout:
            if isinstance(selector_or_timeout, (int, float)):
                timeout = selector_or_timeout
            elif isinstance(selector_or_timeout, str):
                if selector_or_timeout.startswith("//"):
                    xpath = selector_or_timeout
                else:
                    selector = selector_or_timeout

        if len([item for item in [selector, xpath, timeout] if item]) > 1:
            raise ValueError(
                "Wait options must contain either a selector, an xpath, or a timeout"
            )

        if selector:
            await page.wait_for_selector(selector, **options)
        elif xpath:
            await page.wait_for_selector(f"xpath={xpath}", **options)
        elif timeout:
            await asyncio.sleep(timeout / 1000)

    async def goto(self, page: Page, request: ActionRequest):
        url = request.action.payload()["url"]
        cookies = request.cookies
        navigation_options = self.map_navigation_options(
            request.action.navigation_options
        )
        await page.goto(url, **navigation_options)
        wait_options = request.action.payload().get("waitOptions", {}) or {}
        await self.wait_with_options(page, wait_options)
        response_html = await page.content()

        return {
            "html": response_html,
            "cookies": cookies,
        }

    async def click(self, page: Page, request: ActionRequest):
        selector = request.action.payload().get("selector")
        cookies = request.cookies
        click_options = self.map_click_options(request.action.click_options)
        await page.click(selector, **click_options)
        wait_options = request.action.payload().get("waitOptions", {}) or {}
        await self.wait_with_options(page, wait_options)
        response_html = await page.content()

        return {
            "html": response_html,
            "cookies": cookies,
        }

    async def go_back(self, page: Page, request: ActionRequest):
        cookies = request.cookies
        navigation_options = self.map_navigation_options(
            request.action.navigation_options
        )
        await page.go_back(**navigation_options)
        wait_options = request.action.payload().get("waitOptions", {}) or {}
        await self.wait_with_options(page, wait_options)
        response_html = await page.content()

        return {
            "html": response_html,
            "cookies": cookies,
        }

    async def go_forward(self, page: Page, request: ActionRequest):
        cookies = request.cookies
        navigation_options = self.map_navigation_options(
            request.action.navigation_options
        )
        await page.go_forward(**navigation_options)
        wait_options = request.action.payload().get("waitOptions", {}) or {}
        await self.wait_with_options(page, wait_options)
        response_html = await page.content()

        return {
            "html": response_html,
            "cookies": cookies,
        }

    async def screenshot(self, page: Page, request: ActionRequest):
        screenshot_options = request.action.options or {}
        screenshot_bytes = await page.screenshot(
            **self.map_screenshot_options(screenshot_options)
        )
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        return {
            "screenshot": screenshot_base64,
        }

    async def scroll(self, page: Page, request: ActionRequest):
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

        return {
            "html": response_html,
            "cookies": cookies,
        }

    @staticmethod
    async def fill_form(page: Page, request: ActionRequest):
        input_mapping = request.action.payload().get("inputMapping")
        submit_button = request.action.payload().get("submitButton", None)
        cookies = request.cookies

        for selector, params in input_mapping.items():
            text = params.get("value", None)
            delay = params.get("delay", 0)
            await page.type(selector, text=text, delay=delay)

        if submit_button:
            await page.click(submit_button)

        response_html = await page.content()

        return {
            "html": response_html,
            "cookies": cookies,
        }

    async def compose(self, page: Page, request: ActionRequest):
        for action in request.action.actions:
            response_data = await self.action_map[action.endpoint](
                page,
                request.replace(action=action),
            )
        return response_data

    async def action(self, request: ActionRequest):
        raise NotImplementedError("CustomJsAction is not available in local mode")

    async def recaptcha_solver(self, request: ActionRequest):
        raise NotImplementedError("RecaptchaSolver is not available in local mode")

    async def har(self, request: ActionRequest):
        raise NotImplementedError("Har is not available in local mode")
