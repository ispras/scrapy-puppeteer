from . import BrowserManager


class ServiceBrowserManager(BrowserManager):
    def __init__(self):
        super().__init__()

    def download_request(self, request, spider):
        return request
