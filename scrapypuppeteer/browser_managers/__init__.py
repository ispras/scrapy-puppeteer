__all__ = ["BrowserManager"]

from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import Union

from scrapy import Request
from scrapy.utils.defer import deferred_from_coro
from twisted.internet.defer import Deferred


class BrowserManager(ABC):
    @abstractmethod
    def _download_request(self, request: Request, spider) -> Union[Coroutine, Request]:
        ...

    @abstractmethod
    async def _start_browser_manager(self) -> None:
        ...

    @abstractmethod
    async def _stop_browser_manager(self) -> None:
        ...

    def download_request(self, request: Request, spider) -> Union[Deferred, Request]:
        coro_or_request = self._download_request(request, spider)
        if isinstance(coro_or_request, Coroutine):
            return deferred_from_coro(coro_or_request)
        return coro_or_request

    def start_browser_manager(self) -> Deferred:
        return deferred_from_coro(self._start_browser_manager())

    def stop_browser_manager(self) -> Deferred:
        return deferred_from_coro(self._stop_browser_manager())
