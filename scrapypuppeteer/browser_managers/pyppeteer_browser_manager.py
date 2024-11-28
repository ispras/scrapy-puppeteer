import asyncio
import base64
from json import dumps
from typing import Dict, Callable, Awaitable, Any, Union

from pyppeteer import launch
from scrapy.http import TextResponse

from scrapypuppeteer.browser_managers import BrowserManager, ContextManager
from scrapypuppeteer.request import CloseContextRequest, PuppeteerRequest, ActionRequest


class PyppeteerContextManager(ContextManager):
    @classmethod
    async def async_init(cls):
        browser = await launch(headless=False)
        return cls(browser)

    @staticmethod
    async def _create_context(browser):
        return await browser.createIncognitoBrowserContext()

    @staticmethod
    async def _create_page(context):
        return await context.newPage()


class PyppeteerBrowserManager(BrowserManager):
    def __init__(self):
        self.__flag = False
        self.context_manager: Union[PyppeteerContextManager, None] = None
        self.action_map: Dict[
            str, Callable[[..., ActionRequest], Awaitable[Dict[str, Any]]]
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
        if isinstance(request, PuppeteerRequest):
            return self.__perform_action(request)

        if isinstance(request, CloseContextRequest):
            return self.close_contexts(request)

    async def _start_browser_manager(self) -> None:
        if not self.__flag:
            self.__flag = True
            self.context_manager = await PyppeteerContextManager.async_init()

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

    def close_contexts(self, request: CloseContextRequest):
        self.context_manager.close_contexts(request)

    async def wait_with_options(self, page, wait_options: dict):
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
            await page.waitForSelector(selector, options)
        elif xpath:
            await page.waitForXPath(xpath, options)
        elif timeout:
            await asyncio.sleep(timeout / 1000)

    async def goto(self, page, request: ActionRequest):
        url = request.action.payload()["url"]
        cookies = request.cookies
        navigation_options = request.action.navigation_options
        await page.goto(url, navigation_options)
        wait_options = request.action.payload().get("waitOptions", {}) or {}
        await self.wait_with_options(page, wait_options)
        response_html = await page.content()

        return {
            "html": response_html,
            "cookies": cookies,
        }

    async def click(self, page, request: ActionRequest):
        selector = request.action.payload().get("selector")
        cookies = request.cookies
        click_options = request.action.click_options or {}
        navigation_options = request.action.navigation_options or {}
        options = {**click_options, **navigation_options}
        await page.click(selector, options)
        wait_options = request.action.payload().get("waitOptions", {}) or {}
        await self.wait_with_options(page, wait_options)
        response_html = await page.content()

        return {
            "html": response_html,
            "cookies": cookies,
        }

    async def go_back(self, page, request: ActionRequest):
        cookies = request.cookies
        navigation_options = request.action.navigation_options
        await page.goBack(navigation_options)
        wait_options = request.action.payload().get("waitOptions", {}) or {}
        await self.wait_with_options(page, wait_options)
        response_html = await page.content()

        return {
            "html": response_html,
            "cookies": cookies,
        }

    async def go_forward(self, page, request: ActionRequest):
        cookies = request.cookies
        navigation_options = request.action.navigation_options
        await page.goForward(navigation_options)
        wait_options = request.action.payload().get("waitOptions", {}) or {}
        await self.wait_with_options(page, wait_options)
        response_html = await page.content()

        return {
            "html": response_html,
            "cookies": cookies,
        }

    async def screenshot(self, page, request: ActionRequest):
        request_options = request.action.options or {}
        screenshot_options = {"encoding": "binary"}
        screenshot_options.update(request_options)
        screenshot_bytes = await page.screenshot(screenshot_options)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        return {
            "screenshot": screenshot_base64,
        }

    async def scroll(self, page, request: ActionRequest):
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

    async def fill_form(self, page, request: ActionRequest):
        input_mapping = request.action.payload().get("inputMapping")
        submit_button = request.action.payload().get("submitButton", None)
        cookies = request.cookies

        for selector, params in input_mapping.items():
            value = params.get("value", None)
            delay = params.get("delay", 0)
            await page.type(selector, value, {"delay": delay})

        if submit_button:
            await page.click(submit_button)

        response_html = await page.content()

        return {
            "html": response_html,
            "cookies": cookies,
        }

    async def compose(self, page, request: ActionRequest):
        for action in request.action.actions:
            response_data = await self.action_map[action.endpoint](
                page,
                request.replace(action=action),
            )
        return response_data

    async def action(self, request: PuppeteerRequest):
        raise ValueError("CustomJsAction is not available in local mode")

    async def recaptcha_solver(self, request: PuppeteerRequest):
        raise ValueError("RecaptchaSolver is not available in local mode")

    async def har(self, request: PuppeteerRequest):
        raise ValueError("Har is not available in local mode")
