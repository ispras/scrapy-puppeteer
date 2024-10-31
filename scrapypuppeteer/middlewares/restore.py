import json
import logging
from http import HTTPStatus
from typing import Union, Dict

from scrapy.crawler import Crawler

from scrapypuppeteer.actions import Compose
from scrapypuppeteer.request import ActionRequest, PuppeteerRequest
from scrapypuppeteer.response import PuppeteerResponse


class PuppeteerContextRestoreDownloaderMiddleware:
    """
        This middleware allows you to recover puppeteer context.
        The middleware supposes that restored requests
        would have the same effect as original requests.

        If you want to recover puppeteer context starting from the specified first request provide
    `recover_context` meta-key with `True` value.

        The middleware uses additionally these meta-keys, do not use them, because their changing
    could possibly (almost probably) break determined behaviour:
    `__request_binding`

        Settings:

    RESTORING_LENGTH: int = 1 - number of restorable requests in a sequence.
    N_RETRY_RESTORING: int = 1 - number of tries to restore a context.
    """

    restore_logger = logging.getLogger(__name__)

    N_RETRY_RESTORING_SETTING = "N_RETRY_RESTORING"
    RESTORING_LENGTH_SETTING = "RESTORING_LENGTH"

    def __init__(self, restoring_length: int, n_retry_restoring: int):
        self.restoring_length = restoring_length
        self.n_retry_restoring = n_retry_restoring
        self.context_actions: Dict[str, Compose] = {}

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        restoring_length = crawler.settings.get(cls.RESTORING_LENGTH_SETTING, 1)
        if not isinstance(restoring_length, int):
            raise TypeError(
                f"`{cls.RESTORING_LENGTH_SETTING}` must be an integer, got {type(restoring_length)}"
            )
        elif restoring_length < 1:
            raise ValueError(
                f"`{cls.RESTORING_LENGTH_SETTING}` must be greater than or equal to 1, got {restoring_length}"
            )

        n_retry_restoring = crawler.settings.get(cls.N_RETRY_RESTORING_SETTING, 1)
        if not isinstance(n_retry_restoring, int):
            raise TypeError(
                f"`{cls.N_RETRY_RESTORING_SETTING}` must be an integer, got {type(n_retry_restoring)}"
            )
        elif n_retry_restoring < 1:
            raise ValueError(
                f"`{cls.N_RETRY_RESTORING_SETTING}` must be greater than or equal to 1, got {n_retry_restoring}"
            )

        return cls(restoring_length, n_retry_restoring)

    def process_request(self, request, spider):
        if not isinstance(request, PuppeteerRequest):
            return None

        if not request.meta.pop("recover_context", False):
            return None

        if request.context_id or request.page_id:
            self.restore_logger.warning(
                f"Request {request} is not in the beginning of the request-response sequence."
                "Cannot 'restore' this sequence, skipping."
            )
            return None

        request.meta["__request_binding"] = True
        return None

    def process_response(self, request, response, spider):
        puppeteer_request: Union[PuppeteerRequest, None] = request.meta.get(
            "puppeteer_request", None
        )
        request_binding = puppeteer_request is not None and puppeteer_request.meta.get(
            "__request_binding", False
        )

        if isinstance(response, PuppeteerResponse):
            if request_binding:
                self.context_actions[response.context_id] = Compose(request.action)
            elif response.context_id in self.context_actions:
                # Update actions in context
                self._update_context_actions(request, response)
        elif (
            puppeteer_request is not None
            and response.status == HTTPStatus.UNPROCESSABLE_ENTITY
        ):
            # One PuppeteerRequest has failed with 422 error
            if request_binding:
                # Could not get context, retry
                if (
                    request.meta.get("__request_binding_count", 0)
                    < self.n_retry_restoring
                ):
                    new_request = request.copy()
                    new_request.meta["__request_binding_count"] += 1
                    return new_request
            else:
                return self._restore_context(puppeteer_request, response)
        return response

    def _update_context_actions(
        self, request: ActionRequest, response: PuppeteerResponse
    ):
        context_id = response.context_id
        context_actions = self.context_actions[context_id]

        if len(context_actions.actions) > self.restoring_length:
            self.__delete_context(
                context_id,
                f"Too many actions in context ({context_id}). Deleting it.",
            )
        else:
            self.context_actions[response.context_id] = Compose(
                context_actions,
                request.action,
            )

    def _restore_context(self, puppeteer_request: PuppeteerRequest, response):
        context_id = json.loads(response.text).get("contextId", None)

        if context_id in self.context_actions:
            # Restoring
            restoring_request = puppeteer_request.replace(
                action=Compose(
                    self.context_actions.pop(context_id), puppeteer_request.action
                ),
                context_id=None,
                page_id=None,
            )
            restoring_request.meta["__request_binding"] = True
            self.restore_logger.log(
                level=logging.DEBUG,
                msg=f"Restoring the context with context_id {context_id}",
            )
            return restoring_request

        self.restore_logger.warning(f"Context_id {context_id} not in context_actions.")
        return response

    def __delete_context(self, context_id: str, reason: Union[str, None]):
        del self.context_actions[context_id]

        if reason is not None:
            self.restore_logger.log(level=logging.INFO, msg=reason)
