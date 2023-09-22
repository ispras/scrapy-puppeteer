import argparse
import json
import os
import random
import sys
from pathlib import Path
from subprocess import PIPE, Popen
from typing import Dict
from urllib.parse import urlencode

from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory
from twisted.internet.task import deferLater
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET, GzipEncoderFactory, Site
from twisted.web.static import File
from twisted.web.util import redirectTo

from scrapy.utils.python import to_bytes, to_unicode

from secrets import token_hex


def getarg(request, name, default=None, type=None):
    if name in request.args:
        value = request.args[name][0]
        if type is not None:
            value = type(value)
        return value
    return default


def get_mockserver_env() -> Dict[str, str]:
    """Return a OS environment dict suitable to run mockserver processes."""

    tests_path = Path(__file__).parent.parent
    pythonpath = str(tests_path) + os.pathsep + os.environ.get("PYTHONPATH", "")
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath
    return env


class PayloadResource(resource.Resource):
    """
    A testing resource which renders itself as the contents of the request body
    as long as the request body is 100 bytes long, otherwise which renders
    itself as C{"ERROR"}.
    """

    def render(self, request):
        data = request.content.read()
        content_length = request.requestHeaders.getRawHeaders(b"content-length")[0]
        if len(data) != 100 or int(content_length) != 100:
            return b"ERROR"
        return data


class LeafResource(resource.Resource):
    isLeaf = True

    def deferRequest(self, request, delay, f, *a, **kw):
        def _cancelrequest(_):
            # silence CancelledError
            d.addErrback(lambda _: None)
            d.cancel()

        d = deferLater(reactor, delay, f, *a, **kw)
        request.notifyFinish().addErrback(_cancelrequest)
        return d


class GoTo(LeafResource):
    def render_POST(self, request):
        page_id = getarg(request, b"pageId", default=None, type=str)
        context_id = getarg(request, b"contextId", default=None, type=str)
        close_page = getarg(request, b"closePage", default=0, type=bool)

        self.deferRequest(request, 0, self._render_request, request, page_id, context_id, close_page)
        return NOT_DONE_YET

    def _render_request(self, request, page_id, context_id, close_page):
        request.setHeader(b"Content-Type", b"application/json")
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


class Click(LeafResource):
    def render_POST(self, request):
        page_id = getarg(request, b"pageId", default=None, type=str)
        context_id = getarg(request, b"contextId", default=None, type=str)
        close_page = getarg(request, b"closePage", default=0, type=bool)

        self.deferRequest(request, 0, self._render_request, request, page_id, context_id, close_page)
        return NOT_DONE_YET

    def _render_request(self, request, page_id, context_id, close_page):
        request.setHeader(b"Content-Type", b"application/json")
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


class CloseContext(LeafResource):
    def render_POST(self, request):
        self.deferRequest(request, 0, self._render_request, request)
        return NOT_DONE_YET

    def _render_request(self, request):
        request.finish()


class Screenshot(LeafResource):
    def render_POST(self, request):
        page_id = getarg(request, b"pageId", default=None, type=str)
        context_id = getarg(request, b"contextId", default=None, type=str)
        close_page = getarg(request, b"closePage", default=0, type=bool)

        self.deferRequest(request, 0, self._render_request, request, page_id, context_id, close_page)
        return NOT_DONE_YET

    def _render_request(self, request, page_id, context_id, close_page):
        request.setHeader(b"Content-Type", b"application/json")
        from base64 import b64encode
        from json import dumps
        with open("./tests/scrapy_logo.png", 'rb') as image:
            response_data = {
                'screenshot': b64encode(image.read()).decode(),
            }
        request.write(to_bytes(dumps(response_data)))
        request.finish()


class Follow(LeafResource):
    def render(self, request):
        total = getarg(request, b"total", 100, type=int)
        show = getarg(request, b"show", 1, type=int)
        order = getarg(request, b"order", b"desc")
        maxlatency = getarg(request, b"maxlatency", 0, type=float)
        n = getarg(request, b"n", total, type=int)
        if order == b"rand":
            nlist = [random.randint(1, total) for _ in range(show)]
        else:  # order == "desc"
            nlist = range(n, max(n - show, 0), -1)

        lag = random.random() * maxlatency
        self.deferRequest(request, lag, self.renderRequest, request, nlist)
        return NOT_DONE_YET

    def renderRequest(self, request, nlist):
        s = """<html> <head></head> <body>"""
        args = request.args.copy()
        for nl in nlist:
            args[b"n"] = [to_bytes(str(nl))]
            argstr = urlencode(args, doseq=True)
            s += f"<a href='/follow?{argstr}'>follow {nl}</a><br>"
        s += """</body>"""
        request.write(to_bytes(s))
        request.finish()


class Delay(LeafResource):
    def render_GET(self, request):
        n = getarg(request, b"n", 1, type=float)
        b = getarg(request, b"b", 1, type=int)
        if b:
            # send headers now and delay body
            request.write("")
        self.deferRequest(request, n, self._delayedRender, request, n)
        return NOT_DONE_YET

    def _delayedRender(self, request, n):
        request.write(to_bytes(f"Response delayed for {n:.3f} seconds\n"))
        request.finish()


class Status(LeafResource):
    def render_GET(self, request):
        n = getarg(request, b"n", 200, type=int)
        request.setResponseCode(n)
        return b""


class Raw(LeafResource):
    def render_GET(self, request):
        request.startedWriting = 1
        self.deferRequest(request, 0, self._delayedRender, request)
        return NOT_DONE_YET

    render_POST = render_GET

    def _delayedRender(self, request):
        raw = getarg(request, b"raw", b"HTTP 1.1 200 OK\n")
        request.startedWriting = 1
        request.write(raw)
        request.channel.transport.loseConnection()
        request.finish()


class Echo(LeafResource):
    def render_GET(self, request):
        output = {
            "headers": dict(
                (to_unicode(k), [to_unicode(v) for v in vs])
                for k, vs in request.requestHeaders.getAllRawHeaders()
            ),
            "body": to_unicode(request.content.read()),
        }
        return to_bytes(json.dumps(output))

    render_POST = render_GET


class RedirectTo(LeafResource):
    def render(self, request):
        goto = getarg(request, b"goto", b"/")
        # we force the body content, otherwise Twisted redirectTo()
        # returns HTML with <meta http-equiv="refresh"
        redirectTo(goto, request)
        return b"redirecting..."


class Partial(LeafResource):
    def render_GET(self, request):
        request.setHeader(b"Content-Length", b"1024")
        self.deferRequest(request, 0, self._delayedRender, request)
        return NOT_DONE_YET

    def _delayedRender(self, request):
        request.write(b"partial content\n")
        request.finish()


class Drop(Partial):
    def _delayedRender(self, request):
        abort = getarg(request, b"abort", 0, type=int)
        request.write(b"this connection will be dropped\n")
        tr = request.channel.transport
        try:
            if abort and hasattr(tr, "abortConnection"):
                tr.abortConnection()
            else:
                tr.loseConnection()
        finally:
            request.finish()


class ArbitraryLengthPayloadResource(LeafResource):
    def render(self, request):
        return request.content.read()


class Root(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild(b"goto", GoTo())
        self.putChild(b"click", Click())
        self.putChild(b"close_context", CloseContext())
        self.putChild(b"screenshot", Screenshot())
        self.putChild(b"status", Status())
        self.putChild(b"follow", Follow())
        self.putChild(b"delay", Delay())
        self.putChild(b"partial", Partial())
        self.putChild(b"drop", Drop())
        self.putChild(b"raw", Raw())
        self.putChild(b"echo", Echo())
        self.putChild(b"payload", PayloadResource())
        self.putChild(
            b"xpayload",
            resource.EncodingResourceWrapper(PayloadResource(), [GzipEncoderFactory()]),
        )
        self.putChild(b"alpayload", ArbitraryLengthPayloadResource())
        try:
            from tests import tests_datadir

            self.putChild(b"files", File(str(Path(tests_datadir, "test_site/files/"))))
        except Exception:
            pass
        self.putChild(b"redirect-to", RedirectTo())

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
