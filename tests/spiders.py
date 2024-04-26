from scrapy import Spider
from scrapypuppeteer import PuppeteerRequest
from scrapypuppeteer.actions import (
    GoTo,
    GoForward,
    GoBack,
    Click,
    Screenshot,
    CustomJsAction,
    RecaptchaSolver,
)


class MockServerSpider(Spider):
    def __init__(self, mockserver=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mockserver = mockserver


class MetaSpider(MockServerSpider):
    name = "meta"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.meta = {}

    def closed(self, reason):
        self.meta["close_reason"] = reason

    @staticmethod
    def errback(failure):
        print(failure)


class GoToSpider(MetaSpider):
    name = "goto"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls_visited = []

    def start_requests(self):
        yield PuppeteerRequest(
            GoTo("https://some_url.com"),
            callback=self.parse,
            errback=self.errback,
            close_page=False,
        )

    def parse(self, response, **kwargs):
        body = b"""
            <html> <head></head> <body></body>
        """
        if response.body == body:
            self.urls_visited.append(response.url)


class ClickSpider(MetaSpider):
    name = "click"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls_visited = []

    def start_requests(self):
        yield PuppeteerRequest(
            GoTo("https://some_url.com"),
            callback=self.click,
            errback=self.errback,
            close_page=False,
        )

    def click(self, response, **kwargs):
        yield response.follow(
            Click("the_selector"),
            callback=self.parse,
            errback=self.errback,
            close_page=False,
        )

    def parse(self, response, **kwargs):
        body = b"""
            <html> <head></head> <body>clicked</body>
        """
        if response.body == body:
            self.urls_visited.append(response.url)


class ScreenshotSpider(MetaSpider):
    name = "screenshot"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls_visited = []

    def start_requests(self):
        yield PuppeteerRequest(
            GoTo("https://some_url.com"),
            callback=self.screenshot,
            errback=self.errback,
            close_page=False,
        )

    def screenshot(self, response, **kwargs):
        yield response.follow(
            Screenshot(), callback=self.parse, errback=self.errback, close_page=False
        )

    def parse(self, response, **kwargs):
        from base64 import b64encode

        with open("./tests/scrapy_logo.png", "rb") as image:
            if b64encode(image.read()).decode() == response.screenshot:
                self.urls_visited.append(response.url)


class CustomJsActionSpider(MetaSpider):
    name = "custom_js_action"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls_visited = []

    def start_requests(self):
        yield PuppeteerRequest(
            GoTo("https://some_url.com"),
            callback=self.action,
            errback=self.errback,
            close_page=False,
        )

    def action(self, response, **kwargs):
        js_function = """
            some js function
        """
        yield response.follow(
            CustomJsAction(js_function),
            callback=self.parse,
            errback=self.errback,
            close_page=False,
        )

    def parse(self, response, **kwargs):
        response_data = {"field": "Hello!"}
        if response.data == response_data:
            self.urls_visited.append(response.url)


class GoBackForwardSpider(MetaSpider):
    name = "go_back_forward"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls_visited = []

    def start_requests(self):
        yield PuppeteerRequest(
            GoTo("https://some_url.com"),
            callback=self.go_next,
            errback=self.errback,
            close_page=False,
        )

    def go_next(self, response, **kwargs):
        yield response.follow(
            GoTo("/article"),
            callback=self.go_back,
            errback=self.errback,
            close_page=False,
        )

    def go_back(self, response, **kwargs):
        yield response.follow(
            GoBack(), callback=self.go_forward, errback=self.errback, close_page=False
        )

    def go_forward(self, response, **kwargs):
        body = b"""
            <html> <head></head> <body>went back</body>
        """

        assert response.body == body
        yield response.follow(
            GoForward(), callback=self.parse, errback=self.errback, close_page=False
        )

    def parse(self, response, **kwargs):
        body = b"""
            <html> <head></head> <body>went forward</body>
        """
        if response.body == body:
            self.urls_visited.append(response.url)


class RecaptchaSolverSpider(MetaSpider):
    name = "recaptcha_solver"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls_visited = []

    def start_requests(self):
        yield PuppeteerRequest(
            GoTo("https://some_url.com/with_captcha"),
            callback=self.solve_recaptcha,
            errback=self.errback,
            close_page=False,
        )

    def solve_recaptcha(self, response, **kwargs):
        yield response.follow(
            RecaptchaSolver(solve_recaptcha=True),
            callback=self.parse,
            errback=self.errback,
            close_page=False,
        )

    def parse(self, response, **kwargs):
        if response.data["recaptcha_data"]["captchas"] == [1]:
            self.urls_visited.append(response.url)
