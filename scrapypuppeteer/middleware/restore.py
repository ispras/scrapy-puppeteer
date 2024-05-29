import json
import logging

from typing import Union
from http import HTTPStatus

from scrapy.crawler import Crawler
from scrapy.exceptions import IgnoreRequest

from scrapypuppeteer.response import PuppeteerResponse
from scrapypuppeteer.request import PuppeteerRequest

restore_logger = logging.getLogger(__name__)


class PuppeteerContextRestoreDownloaderMiddleware:
    """
        This middleware allows you to recover puppeteer context.

        If you want to recover puppeteer context starting from the specified first request provide
    `recover_context` meta-key with `True` value.

        The middleware uses additionally these meta-keys, do not use them, because their changing
    could possibly (almost probably) break determined behaviour:
    ...

        Settings:

    RESTORING_LENGTH: int = 1 - number of restorable requests in a sequence.
    N_RETRY_RESTORING: int = 1 - number of tries to restore a context.
    """

    """
        WORK SCHEME:

        cases:
        1.) First PptrReq (without Context), Its response is good. After some request-response sequence it fails.
            Trying to recover it N times.
        2.) First PptrReq (without Context), Its response is bad. We need to try to recover it N times.

        For recovering we use context. If we have it we get first request in sequence and trying to recover everything
            from the beginning.
        If we don't have it then we can send the request One more time in process_response until we get it.
    """

    N_RETRY_RESTORING_SETTING = "N_RETRY_RESTORING"
    RESTORING_LENGTH_SETTING = "RESTORING_LENGTH"

    def __init__(self, restoring_length: int, n_retry_restoring: int):
        self.restoring_length = restoring_length
        self.n_retry_restoring = n_retry_restoring
        self.context_requests = {}
        self.context_length = {}

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        restoring_length = crawler.settings.get(cls.RESTORING_LENGTH_SETTING, 1)
        if not isinstance(restoring_length, int):
            raise TypeError(f"`{cls.RESTORING_LENGTH_SETTING}` must be an integer, got {type(restoring_length)}")
        elif restoring_length < 1:
            raise ValueError(f"`{cls.RESTORING_LENGTH_SETTING}` must be greater than or equal to 1")

        n_retry_restoring = crawler.settings.get(cls.N_RETRY_RESTORING_SETTING, 1)
        if not isinstance(n_retry_restoring, int):
            raise TypeError(f"`{cls.N_RETRY_RESTORING_SETTING}` must be an integer, got {type(n_retry_restoring)}")
        elif n_retry_restoring < 1:
            raise ValueError(f"`{cls.N_RETRY_RESTORING_SETTING}` must be greater than or equal to 1")

        return cls(restoring_length, n_retry_restoring)

    @staticmethod
    def process_request(request, spider):
        if not isinstance(request, PuppeteerRequest):
            return None

        if not request.meta.pop('recover_context', False):
            return None

        if request.context_id or request.page_id:
            raise IgnoreRequest(f"Request {request} is not in the beginning of the request-response sequence")

        request.meta['__request_binding'] = True
        request.dont_filter = True
        return None

    def process_response(self, request, response, spider):
        puppeteer_request: Union[PuppeteerRequest, None] = request.meta.get('puppeteer_request', None)
        request_binding = puppeteer_request is not None and puppeteer_request.meta.get('__request_binding', False)

        if isinstance(response, PuppeteerResponse):
            if request_binding:
                self._bind_context(request, response)
            if response.context_id in self.context_length:
                # Update number of actions in context
                self.context_length[response.context_id] += 1
        elif puppeteer_request is not None and response.status == HTTPStatus.UNPROCESSABLE_ENTITY:
            # One PuppeteerRequest has failed with 422 error
            if request_binding:
                # Could not get context, retry
                if request.meta.get('__restore_count', 0) < self.n_retry_restoring:
                    request.meta['__restore_count'] += 1
                    return request
            else:
                return self._restore_context(response)
        return response

    def _bind_context(self, request, response):
        if request.meta.get('__context_id', None) is not None:
            # Need to update context_id
            self.__delete_context(request.meta['__context_id'], None)
        restoring_request = request.copy()
        restoring_request.meta['__restore_count'] = restoring_request.meta.get('__restore_count', 0)
        restoring_request.meta['__context_id'] = response.context_id
        self.context_requests[response.context_id] = restoring_request
        self.context_length[response.context_id] = 0

    def _restore_context(self, response):
        context_id = json.loads(response.text).get('contextId', None)

        if context_id in self.context_requests:
            restoring_request = self.context_requests[context_id]

            if self.context_length[context_id] >= self.restoring_length + 1:
                # Too many actions in context
                self.__delete_context(context_id, f"Too many actions in context ({restoring_request}). Deleting it.")
            elif restoring_request.meta['__restore_count'] >= self.n_retry_restoring:
                # Too many retries
                self.__delete_context(context_id, f"Too many retries in context ({restoring_request}). Deleting it.")
            else:
                # Restoring
                restoring_request.meta['__restore_count'] += 1
                restore_logger.log(level=logging.DEBUG,
                                   msg=f"Restoring the request {restoring_request}")
                self.context_length[context_id] = 1
                return restoring_request
        return response

    def __delete_context(self, context_id: str, reason: Union[str, None]):
        del self.context_length[context_id]
        del self.context_requests[context_id]

        if reason is not None:
            restore_logger.log(level=logging.INFO,
                               msg=reason)
