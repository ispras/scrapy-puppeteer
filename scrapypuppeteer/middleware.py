import json
from urllib.parse import urljoin, urlencode

from scrapy import Request
from scrapy.http import Headers, TextResponse

from scrapypuppeteer import PuppeteerRequest, PuppeteerResponse
from scrapypuppeteer.actions import Goto


class PuppeteerServiceDownloaderMiddleware:
    def __init__(self, service_url: str):
        self.service_base_url = service_url

    @classmethod
    def from_crawler(cls, crawler):
        service_url = crawler.settings.get('PUPPETEER_SERVICE_URL')
        if service_url is None:
            raise ValueError('Puppeteer service URL must be provided')
        return cls(service_url)

    def process_request(self, request, spider):
        if not isinstance(request, PuppeteerRequest):
            return

        action = request.action
        if isinstance(action, Goto):
            service_url = urljoin(self.service_base_url, 'goto')
            service_params = {}
            if request.context_id is not None:
                service_params['context_id'] = request.context_id
            if request.page_id is not None:
                service_params['page_id'] = request.page_id
            service_url += '?' + urlencode(service_params)
            return request.replace(
                cls=Request,
                url=service_url,
                method='POST',
                headers=Headers({'Content-Type': 'application/json'}),
                body=json.dumps({
                    'url': action.url,
                    'options': action.options,
                    'closePage': request.close_page
                }),
                dont_filter=True,
                meta={
                    'puppeteer_request': request,
                    'dont_obey_robotstxt': True
                }
            )

    def process_response(self, request, response, spider):
        if not isinstance(response, TextResponse):
            return response

        puppeteer_request = request.meta.get('puppeteer_request')
        if puppeteer_request is None:
            return response

        response_data = json.loads(response.text)
        response = PuppeteerResponse(
            url=puppeteer_request.url,
            body=response_data.get('html'),
            encoding='utf-8',
            puppeteer_request=puppeteer_request,
            context_id=response_data.get('context_id'),
            page_id=response_data.get('page_id')
        )
        return response
