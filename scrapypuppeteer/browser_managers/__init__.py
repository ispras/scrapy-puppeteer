__all__ = ["BrowserManager", "ContextManager"]

import uuid
from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import Union, Dict

from scrapy import Request
from scrapy.utils.defer import deferred_from_coro
from twisted.internet.defer import Deferred

from scrapypuppeteer import CloseContextRequest


class ContextManager(ABC):
    def __init__(self, browser):
        self.browser = browser
        self.contexts: Dict[str, ...] = {}
        self.pages: Dict[str, ...] = {}
        self.context2page: Dict[str, str] = {}

    @classmethod
    @abstractmethod
    async def async_init(cls):
        ...

    @staticmethod
    @abstractmethod
    async def _create_context(browser):
        ...

    @staticmethod
    @abstractmethod
    async def _create_page(context):
        ...

    async def check_context_and_page(self, context_id, page_id):
        if not context_id or not page_id:
            context_id, page_id = await self.open_new_page()
        return context_id, page_id

    async def open_new_page(self):
        context_id = uuid.uuid4().hex.upper()
        page_id = uuid.uuid4().hex.upper()

        self.contexts[context_id] = await self._create_context(self.browser)
        self.pages[page_id] = await self._create_page(self.contexts[context_id])
        self.context2page[context_id] = page_id

        return context_id, page_id

    def get_page_by_id(self, context_id, page_id):
        return self.pages[page_id]

    async def close_browser(self):
        if self.browser:
            await self.browser.close()

    async def close_contexts(self, request: CloseContextRequest):
        for context_id in request.contexts:
            if context_id in self.contexts:
                await self.contexts[context_id].close()
                page_id = self.context2page.get(context_id)
                self.pages.pop(page_id, None)

                del self.contexts[context_id]
                del self.context2page[context_id]


class BrowserManager(ABC):
    @abstractmethod
    def _download_request(
        self, request: Request, spider
    ) -> Union[Coroutine, Request]:
        ...

    @abstractmethod
    async def _start_browser_manager(self) -> None: ...

    @abstractmethod
    async def _stop_browser_manager(self) -> None: ...

    def download_request(self, request: Request, spider) -> Union[Deferred, Request]:
        coro_or_request = self._download_request(request, spider)
        if isinstance(coro_or_request, Coroutine):
            return deferred_from_coro(coro_or_request)
        return coro_or_request

    def start_browser_manager(self) -> Deferred:
        return deferred_from_coro(self._start_browser_manager())

    def stop_browser_manager(self) -> Deferred:
        return deferred_from_coro(self._stop_browser_manager())
