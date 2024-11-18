__all__ = ["BrowserManager"]

from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import Union

from scrapy import Request


class BrowserManager(ABC):
    @abstractmethod
    def download_request(self, request: Request, spider) -> Union[Coroutine, Request]:
        ...

    # @abstractmethod
    # def close_used_contexts(self):
    #     ...
    #
    # @abstractmethod
    # def process_response(self, middleware, request, response, spider):
    #     ...
