import json
from abc import ABC


class PuppeteerServiceAction:
    endpoint = None
    content_type = 'application/json'

    def serialize_body(self):
        pass


class Goto(PuppeteerServiceAction):
    endpoint = 'goto'

    def __init__(self, url: str, options: dict = None, **kwargs):
        self.url = url
        self.options = options or {}
        self.options.update(kwargs)

    def serialize_body(self):
        return json.dumps({
            'url': self.url,
            'options': self.options
        })


class Click(PuppeteerServiceAction):
    endpoint = 'click'

    def __init__(self, selector: str, click_options: dict = None, wait_options: dict = None):
        self.selector = selector
        self.click_options = click_options or {}
        self.wait_options = wait_options or {}

    def serialize_body(self):
        return json.dumps({
            'selector': self.selector,
            'clickOptions': self.click_options,
            'waitOptions': self.wait_options
        })


class Scroll(PuppeteerServiceAction):
    endpoint = 'scroll'

    def __init__(self, selector: str, wait_options: dict = None):
        self.selector = selector
        self.wait_options = wait_options or {}

    def serialize_body(self):
        return json.dumps({
            'selector': self.selector,
            'waitOptions': self.wait_options
        })


class Screenshot(PuppeteerServiceAction):
    endpoint = 'screenshot'

    def __init__(self, options: dict = None, **kwargs):
        self.options = options or {}
        self.options.update(kwargs)

    def serialize_body(self):
        return json.dumps({
            'options': self.options
        })


class CustomJsAction(PuppeteerServiceAction):
    endpoint = 'action'
    content_type = 'application/javascript'

    def __init__(self, js_action: str):
        self.js_action = js_action

    def serialize_body(self):
        return self.js_action
