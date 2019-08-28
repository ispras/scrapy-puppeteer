import asyncio
from urllib.parse import urljoin

from pyppeteer.page import Page


def goto(url: str, options: dict = None, **kwargs):
    async def _goto(page: Page):
        abs_url = url
        if url.startswith('/'):
            abs_url = urljoin(page.url, url)
        return await page.goto(abs_url, options, **kwargs)

    return _goto
