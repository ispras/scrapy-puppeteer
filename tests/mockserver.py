import argparse
import os
import sys

from pathlib import Path
from subprocess import PIPE, Popen
from typing import Dict
from secrets import token_hex

from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory
from twisted.internet.task import deferLater
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET, Site

from scrapy.utils.python import to_bytes


def getarg(request, name, default=None, type=None):
    if name in request.args:
        value = request.args[name][0]
        if type is not None:
            value = type(value)
        return value
    return default


def get_mockserver_env() -> Dict[str, str]:
    """Return an OS environment dict suitable to run mockserver processes."""

    tests_path = Path(__file__).parent.parent
    pythonpath = str(tests_path) + os.pathsep + os.environ.get("PYTHONPATH", "")
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath
    return env


class LeafResource(resource.Resource):
    isLeaf = True

    def render_POST(self, request):
        page_id = getarg(request, b"pageId", default=None, type=str)
        context_id = getarg(request, b"contextId", default=None, type=str)
        close_page = getarg(request, b"closePage", default=0, type=bool)

        request.setHeader(b"Content-Type", b"application/json")

        self.deferRequest(request, 0, self._render_request, request, page_id, context_id, close_page)
        return NOT_DONE_YET

    def deferRequest(self, request, delay, f, *a, **kw):
        def _cancelrequest(_):
            # silence CancelledError
            d.addErrback(lambda _: None)
            d.cancel()

        d = deferLater(reactor, delay, f, *a, **kw)
        request.notifyFinish().addErrback(_cancelrequest)
        return d

    def _render_request(self, request, page_id, context_id, close_page):
        raise NotImplementedError


class GoTo(LeafResource):
    def _render_request(self, request, page_id, context_id, close_page):
        html = '''
            <html> <head></head> <body></body>
        '''
        from json import dumps
        response_data = {
            'contextId': token_hex(20),
            'pageId': token_hex(20),
            'html': html,
            'cookies': None
        }
        request.write(to_bytes(dumps(response_data)))
        request.finish()


class GoForward(LeafResource):
    def _render_request(self, request, page_id, context_id, close_page):
        html = '''
            <html> <head></head> <body>went forward</body>
        '''
        from json import dumps
        response_data = {
            'contextId': context_id,
            'pageId': page_id,
            'html': html,
            'cookies': None
        }
        request.write(to_bytes(dumps(response_data)))
        request.finish()


class Back(LeafResource):
    def _render_request(self, request, page_id, context_id, close_page):
        html = '''
            <html> <head></head> <body>went back</body>
        '''
        from json import dumps
        response_data = {
            'contextId': context_id,
            'pageId': page_id,
            'html': html,
            'cookies': None
        }
        request.write(to_bytes(dumps(response_data)))
        request.finish()


class Click(LeafResource):
    def _render_request(self, request, page_id, context_id, close_page):
        html = '''
            <html> <head></head> <body>clicked</body>
        '''
        from json import dumps
        response_data = {
            'contextId': context_id,
            'pageId': page_id,
            'html': html,
            'cookies': None
        }
        request.write(to_bytes(dumps(response_data)))
        request.finish()


class Screenshot(LeafResource):
    def _render_request(self, request, page_id, context_id, close_page):
        from base64 import b64encode
        from json import dumps
        with open("./tests/scrapy_logo.png", 'rb') as image:
            response_data = {
                'contextId': context_id,
                'pageId': page_id,
                'screenshot': b64encode(image.read()).decode(),
            }
        request.write(to_bytes(dumps(response_data)))
        request.finish()


class Action(LeafResource):
    def _render_request(self, request, page_id, context_id, close_page):
        from json import dumps
        response_data = {
            'contextId': context_id,
            'pageId': page_id,
            'data': {'field': "Hello!"},
        }
        request.write(to_bytes(dumps(response_data)))
        request.finish()


class CloseContext(LeafResource):
    def _render_request(self, request, page_id, context_id, close_page):
        request.finish()


class Root(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild(b"goto", GoTo())
        self.putChild(b"forward", GoForward())
        self.putChild(b"back", Back())
        self.putChild(b"click", Click())
        self.putChild(b"screenshot", Screenshot())
        self.putChild(b"action", Action())
        self.putChild(b"close_context", CloseContext())

    def getChild(self, name, request):
        return self


class MockServer:
    def __enter__(self):
        self.proc = Popen(
            [sys.executable, "-u", "-m", "tests.mockserver", "-t", "http"],
            stdout=PIPE,
            env=get_mockserver_env(),
        )
        self.http_address = self.proc.stdout.readline().strip().decode("ascii")

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.communicate()

    def url(self, path):
        host = self.http_address.replace("0.0.0.0", "127.0.0.1")
        return host + path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t", "--type", type=str, choices=("http",), default="http"
    )
    args = parser.parse_args()

    if args.type == "http":
        root = Root()
        factory: ServerFactory = Site(root)
        httpPort = reactor.listenTCP(0, factory)


        def print_listening():
            http_host = httpPort.getHost()
            http_address = f"http://{http_host.host}:{http_host.port}"
            print(http_address)

    reactor.callWhenRunning(print_listening)
    reactor.run()
