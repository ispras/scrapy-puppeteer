import warnings

import scrapy.exceptions

from .middlewares import (
    PuppeteerContextRestoreDownloaderMiddleware,
    PuppeteerRecaptchaDownloaderMiddleware,
    PuppeteerServiceDownloaderMiddleware,
)

warnings.warn(
    "Import from `scrapypuppeteer.middleware` is deprecated. "
    "Use `scrapypuppeteer.middlewares` instead.",
    scrapy.exceptions.ScrapyDeprecationWarning,
    stacklevel=2,
)


__all__ = [
    "PuppeteerServiceDownloaderMiddleware",
    "PuppeteerRecaptchaDownloaderMiddleware",
    "PuppeteerContextRestoreDownloaderMiddleware",
]
