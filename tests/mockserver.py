import argparse
import os
import sys
from base64 import b64encode
from json import dumps
from pathlib import Path
from secrets import token_hex
from subprocess import PIPE, Popen
from typing import Dict

from scrapy.utils.python import to_bytes
from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory
from twisted.internet.task import deferLater
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET, Site


def get_arg(request, name, default=None, arg_type=None):
  if name in request.args:
    value = request.args[name][0]
    if arg_type is not None:
      value = arg_type(value)
    return value
  return default


def get_mockserver_env() -> Dict[str, str]:
  """Return an OS environment dict suitable to run mockserver processes."""

  tests_path = Path(__file__).parent.parent
  python_path = str(tests_path) + os.pathsep + os.environ.get("PYTHONPATH", "")
  env = os.environ.copy()
  env["PYTHONPATH"] = python_path
  return env


class LeafResource(resource.Resource):
  isLeaf = True

  def render_POST(self, request):
    page_id = get_arg(request, b"pageId", default=None, arg_type=str)
    context_id = get_arg(request, b"contextId", default=None, arg_type=str)
    close_page = get_arg(request, b"closePage", default=0, arg_type=bool)

    request.setHeader(b"Content-Type", b"application/json")

    self.defer_request(
      request, 0, self.render_request, request, page_id, context_id, close_page
    )
    return NOT_DONE_YET

  @staticmethod
  def defer_request(request, delay, render_func, *args, **kwargs):
    def _cancel_request(_):
      # silence CancelledError
      d.addErrback(lambda _: None)
      d.cancel()

    d = deferLater(reactor, delay, render_func, *args, **kwargs)
    request.notifyFinish().addErrback(_cancel_request)
    return d

  def render_request(self, request, page_id, context_id, close_page):
    request.write(to_bytes(dumps(self._form_response(page_id, context_id, close_page))))
    request.finish()

  def _form_response(self, page_id, context_id, close_page):
    raise NotImplementedError


class GoTo(LeafResource):
  def _form_response(self, page_id, context_id, close_page):
    html = """
            <html> <head></head> <body></body>
        """
    return {
      "contextId": token_hex(20),
      "pageId": token_hex(20),
      "html": html,
      "cookies": None,
    }


class GoForward(LeafResource):
  def _form_response(self, page_id, context_id, close_page):
    html = """
            <html> <head></head> <body>went forward</body>
        """
    return {
      "contextId": context_id,
      "pageId": page_id,
      "html": html,
      "cookies": None,
    }


class Back(LeafResource):
  def _form_response(self, page_id, context_id, close_page):
    html = """
            <html> <head></head> <body>went back</body>
        """
    return {
      "contextId": context_id,
      "pageId": page_id,
      "html": html,
      "cookies": None,
    }


class Click(LeafResource):
  def _form_response(self, page_id, context_id, close_page):
    html = """
            <html> <head></head> <body>clicked</body>
        """
    return {
      "contextId": context_id,
      "pageId": page_id,
      "html": html,
      "cookies": None,
    }


class Screenshot(LeafResource):
  def _form_response(self, page_id, context_id, close_page):
    with open("./tests/scrapy_logo.png", "rb") as image:
      return {
        "contextId": context_id,
        "pageId": page_id,
        "screenshot": b64encode(image.read()).decode(),
      }


class RecaptchaSolver(LeafResource):
  def _form_response(self, page_id, context_id, close_page):
    html = """
            <html> <head></head> <body>there is recaptcha on the page!</body>
        """
    return {
      "contextId": context_id,
      "pageId": page_id,
      "html": html,
      "cookies": None,
      "recaptcha_data": {
        "captchas": [1],  # 1 captcha
        "some_other_fields": [],
      },
    }


class CustomJsAction(LeafResource):
  def _form_response(self, page_id, context_id, close_page):
    return {
      "contextId": context_id,
      "pageId": page_id,
      "data": {"field": "Hello!"},
    }


class CloseContext(LeafResource):
  def render_request(self, request, page_id, context_id, close_page):
    request.finish()


class Root(resource.Resource):
  def __init__(self):
    resource.Resource.__init__(self)
    self.putChild(b"goto", GoTo())
    self.putChild(b"forward", GoForward())
    self.putChild(b"back", Back())
    self.putChild(b"click", Click())
    self.putChild(b"screenshot", Screenshot())
    self.putChild(b"action", CustomJsAction())
    self.putChild(b"recaptcha_solver", RecaptchaSolver())
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


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("-t", "--type", type=str, choices=("http",), default="http")
  args = parser.parse_args()

  if args.type == "http":
    root = Root()
    factory: ServerFactory = Site(root)
    http_port = reactor.listenTCP(0, factory)

    def print_listening():
      http_host = http_port.getHost()
      http_address = f"http://{http_host.host}:{http_host.port}"
      print(http_address)

  reactor.callWhenRunning(print_listening)
  reactor.run()


if __name__ == "__main__":
  main()
