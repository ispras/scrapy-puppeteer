import json
from abc import abstractmethod, ABC


class PuppeteerServiceAction(ABC):

    @property
    @abstractmethod
    def endpoint(self):
        ...

    content_type = 'application/json'

    @abstractmethod
    def serialize_body(self):
        ...


class GoTo(PuppeteerServiceAction):
    """
    Navigate page to given URL.

    :param str url: URL to navigate to. May be relative for following requests.
    :param dict options: Navigation options.

    Available options (see puppeteer `page.goto <https://pptr.dev/#?product=Puppeteer&version=v1.19.0&show=api-pagegotourl-options>`_):

    * ``timeout`` (int): Maximum navigation time in milliseconds, defaults
      to 30 seconds, pass ``0`` to disable timeout. The default value can
      be changed by using the :meth:`setDefaultNavigationTimeout` method.
    * ``waitUntil`` (str|List[str]): When to consider navigation succeeded,
      defaults to ``load``. Given a list of event strings, navigation is
      considered to be successful after all events have been fired. Events
      can be either:

      * ``load``: when ``load`` event is fired.
      * ``domcontentloaded``: when the ``DOMContentLoaded`` event is fired.
      * ``networkidle0``: when there are no more than 0 network connections
        for at least 500 ms.
      * ``networkidle2``: when there are no more than 2 network connections
        for at least 500 ms.

    """

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


class GoForward(PuppeteerServiceAction):
    """
    Navigate to the next page in history.

    :param dict options: Navigation options, same as GoTo action.

    """

    endpoint = 'forward'

    def __init__(self, options: dict = None, **kwargs):
        self.options = options or {}
        self.options.update(kwargs)

    def serialize_body(self):
        return json.dumps({
            'options': self.options
        })


class GoBack(PuppeteerServiceAction):
    """
    Navigate to the previous page in history.

    :param dict options: Navigation options, same as GoTo action.

    """

    endpoint = 'back'

    def __init__(self, options: dict = None, **kwargs):
        self.options = options or {}
        self.options.update(kwargs)

    def serialize_body(self):
        return json.dumps({
            'options': self.options
        })


class Click(PuppeteerServiceAction):
    """
    Click element which matches ``selector``.

    Available click options (see puppeteer `page.click <https://pptr.dev/#?product=Puppeteer&version=v1.19.0&show=api-pageclickselector-options>`_):

    * ``button`` (str): ``left``, ``right``, or ``middle``, defaults to
      ``left``.
    * ``clickCount`` (int): defaults to 1.
    * ``delay`` (int|float): Time to wait between ``mousedown`` and
      ``mouseup`` in milliseconds. defaults to 0.

    Available wait options (see puppeteer `page.waitFor <https://pptr.dev/#?product=Puppeteer&version=v1.19.0&show=api-pagewaitforselectororfunctionortimeout-options-args>`_):

    * ``selectorOrTimeout`` (int|float|str): If it is a selector string or xpath string, wait until
        element which matches that selector appears on page. If it is a number, then it
        is treated as a timeout in milliseconds.

    Response for this action contains page state after click and wait.

    """

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
    """
    Scroll page down or for specific element.

    :param str selector: If provided, scroll this element into view, otherwise scroll down by window
        height.
    :param dict wait_options: Same as in Click action.

    Response for this action contains page state after scroll and wait.

    """

    endpoint = 'scroll'

    def __init__(self, selector: str = None, wait_options: dict = None):
        self.selector = selector
        self.wait_options = wait_options or {}

    def serialize_body(self):
        return json.dumps({
            'selector': self.selector,
            'waitOptions': self.wait_options
        })


class Screenshot(PuppeteerServiceAction):
    """
    Take a screen shot.

    Available options (see puppeteer `page.screenshot <https://pptr.dev/#?product=Puppeteer&version=v1.19.0&show=api-pagescreenshotoptions>`_)

    * ``type`` (str): Specify screenshot type, can be either ``jpeg`` or
      ``png``. Defaults to ``png``.
    * ``quality`` (int): The quality of the image, between 0-100. Not
      applicable to ``png`` image.
    * ``fullPage`` (bool): When true, take a screenshot of the full
      scrollable page. Defaults to ``False``.
    * ``clip`` (dict): An object which specifies clipping region of the
      page. This option should have the following fields:

      * ``x`` (int): x-coordinate of top-left corner of clip area.
      * ``y`` (int): y-coordinate of top-left corner of clip area.
      * ``width`` (int): width of clipping area.
      * ``height`` (int): height of clipping area.

    * ``omitBackground`` (bool): Hide default white background and allow
      capturing screenshot with transparency.

    Response for this action contains screen shot image in base64 encoding.

    """

    endpoint = 'screenshot'

    def __init__(self, options: dict = None, **kwargs):
        self.options = options or {}
        self.options.update(kwargs)

    def serialize_body(self):
        return json.dumps({
            'options': self.options
        })


class CustomJsAction(PuppeteerServiceAction):
    """
    Evaluate custom JavaScript function on page.

    :param str js_action: JavaScript function.

    Expected signature: ``async function action(page, request)``

    Response for this action contains result of the function.

    """

    endpoint = 'action'
    content_type = 'application/javascript'

    def __init__(self, js_action: str):
        self.js_action = js_action

    def serialize_body(self):
        return self.js_action
