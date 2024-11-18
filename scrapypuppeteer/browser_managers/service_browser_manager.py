import json
import logging
from collections import defaultdict
from urllib.parse import urlencode, urljoin

from scrapy.exceptions import DontCloseSpider
from scrapy.http import Headers, Response, TextResponse
from scrapy.utils.log import failure_to_exc_info
from twisted.python.failure import Failure

from scrapypuppeteer.actions import (
    Click,
    Compose,
    FillForm,
    GoBack,
    GoForward,
    GoTo,
    Har,
    RecaptchaSolver,
    Screenshot,
    Scroll,
)
from scrapypuppeteer.browser_managers import BrowserManager


class ServiceBrowserManager(BrowserManager):
    def __init__(self):
        super().__init__()

    def download_request(self, request, spider):
        return request
