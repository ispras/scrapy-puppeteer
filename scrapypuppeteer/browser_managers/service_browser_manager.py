from . import BrowserManager


class ServiceBrowserManager(BrowserManager):
    def __init__(self):
        super().__init__()

    def _download_request(self, request, spider):
        return request

    def _start_browser_manager(self) -> None:
        return

    def _stop_browser_manager(self) -> None:
        return
