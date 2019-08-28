import asyncio
import logging

import pyppeteer
from pyppeteer.browser import BrowserContext
from pyppeteer.network_manager import Response
from pyppeteer.page import Page
from scrapy.http import Headers
from twisted.internet.defer import Deferred

from scrapyppeteer.request import PyppeteerRequest
from scrapyppeteer.response import PyppeteerResponse


pyppeteer_level = logging.INFO
logging.getLogger('websockets.protocol').setLevel(pyppeteer_level)
logging.getLogger('pyppeteer').setLevel(pyppeteer_level)


def as_deferred(future):
    return Deferred.fromFuture(asyncio.ensure_future(future))


class PyppeteerDownloadHandler:
    def __init__(self, settings):
        self._settings = settings.getdict('PYPPETEER_SETTINGS') or {}
        self._browser = None

    def download_request(self, request, spider):
        return as_deferred(self._download_request(request, spider))

    async def _download_request(self, request, spider):
        if not isinstance(request, PyppeteerRequest):
            raise TypeError(f'Expected pyppeteer request, got {type(request)}')

        if self._browser is None:
            self._browser = await pyppeteer.launch(**self._settings)

        browser = self._browser
        context, context_id = await self._get_or_create_context(browser, request.context_id)
        page, page_id = await self._get_or_create_page(context, request.page_id)

        # Headers and cookies - from https://github.com/clemfromspace/scrapy-puppeteer

        # Cookies
        if isinstance(request.cookies, dict):
            await page.setCookie(*[
                {'name': k, 'value': v}
                for k, v in request.cookies.items()
            ])
        else:
            await page.setCookie(request.cookies)

        # The headers must be set using request interception
        # await page.setRequestInterception(True)

        # @page.on('request')
        # async def _handle_headers(pu_request):
        #     overrides = {
        #         'headers': {
        #             k.decode(): ','.join(map(lambda v: v.decode(), v))
        #             for k, v in request.headers.items()
        #         }
        #     }
        #     await pu_request.continue_(overrides=overrides)

        await page.setUserAgent(request.headers['User-Agent'].decode())
        # await page.setExtraHTTPHeaders({
        #     k.decode(): ','.join(map(lambda v: v.decode(), v))
        #     for k, v in request.headers.items()
        # })

        result = await request.action(page)  # TODO exceptions
        content = await page.content()

        response = PyppeteerResponse(
            url=page.url,
            context_id=context_id,
            page_id=page_id,
            status=200,
            body=str.encode(content),
            encoding='utf-8'
        )

        if isinstance(result, Response):
            response.status = result.status
            response.headers = Headers(result.headers)
            response.headers.pop('Content-Encoding', None)  # already decompressed

        if request.close_context:
            await context.close()

        return response

    @staticmethod
    async def _get_or_create_context(browser, context_id) -> (BrowserContext, str):
        context = browser._contexts.get(context_id)
        if context is None:
            context = await browser.createIncognitoBrowserContext()
        return context, context._id

    @staticmethod
    async def _get_or_create_page(context, page_id) -> (Page, str):
        if page_id is not None:
            for target in context.targets():
                if page_id == target._targetId:
                    return target._page, page_id
        page = await context.newPage()
        return page, page.target._targetId

    def close(self):
        return as_deferred(self._close())

    async def _close(self):
        await self._browser.close()
