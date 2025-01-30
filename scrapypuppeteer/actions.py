from abc import ABC, abstractmethod
from typing import List, Tuple


class PuppeteerServiceAction(ABC):
    content_type = "application/json"

    @property
    @abstractmethod
    def endpoint(self): ...

    @abstractmethod
    def payload(self): ...


class GoTo(PuppeteerServiceAction):
    """
    Navigate page to given URL.

    :param str url: URL to navigate to. May be relative for following requests.
    :param dict navigation_options: Navigation options.
    :param dict wait_options: Options specifying wait after navigation.

    Available navigation options (see puppeteer `page.goto
    <https://pptr.dev/#?product=Puppeteer&version=v3.2.0&show=api-pagegotourl-options>`_):

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

    Available wait options (see puppeteer `page.waitFor
    <https://pptr.dev/#?product=Puppeteer&version=v3.2.0&show=api-pagewaitforselectororfunctionortimeout-options-args>`_);

    * ``selectorOrTimeout`` (int|float|str): If it is a selector string or xpath string, wait until
        element which matches that selector appears on page. If it is a number, then it
        is treated as a timeout in milliseconds.``
    * ``options`` (dict): optional parameters to wait on selector
      * ``visible`` (bool): wait for element to be present in DOM and to be visible.
        Defaults to false.
      * ``timeout`` (int|float): maximum time to wait for in milliseconds.
        Defaults to 30000 (30 seconds). Pass 0 to disable timeout.
      * ``hidden`` (bool): wait for element to not be found in the DOM or to be hidden.
      Defaults to false.

    """

    endpoint = "goto"

    def __init__(
        self,
        url: str,
        navigation_options: dict = None,
        wait_options: dict = None,
        har_recording: bool = False,
    ):
        self.url = url
        self.navigation_options = navigation_options
        self.wait_options = wait_options
        self.har_recording = har_recording

    def payload(self):
        return {
            "url": self.url,
            "navigationOptions": self.navigation_options,
            "waitOptions": self.wait_options,
            "harRecording": self.har_recording,
        }


class GoForward(PuppeteerServiceAction):
    """
    Navigate to the next page in history.

    :param dict navigation_options: Navigation options, same as GoTo action.
    :param dict wait_options: Options specifying wait after navigation, same as GoTo action.

    """

    endpoint = "forward"

    def __init__(self, navigation_options: dict = None, wait_options: dict = None):
        self.navigation_options = navigation_options
        self.wait_options = wait_options

    def payload(self):
        return {
            "navigationOptions": self.navigation_options,
            "waitOptions": self.wait_options,
        }


class GoBack(PuppeteerServiceAction):
    """
    Navigate to the previous page in history.

    :param dict navigation_options: Navigation options, same as GoTo action.
    :param dict wait_options: Options specifying wait after navigation, same as GoTo action.

    """

    endpoint = "back"

    def __init__(self, navigation_options: dict = None, wait_options: dict = None):
        self.navigation_options = navigation_options
        self.wait_options = wait_options

    def payload(self):
        return {
            "navigationOptions": self.navigation_options,
            "waitOptions": self.wait_options,
        }


class Click(PuppeteerServiceAction):
    """
    Click element which matches ``selector``.

    :param str selector: Specifies element to click.
    :param dict click_options: Optional parameters for click.
    :param dict wait_options: Options specifying wait after click, same as GoTo action.
    :param dict navigation_options: Navigation options to be used if click results in navigation to
        other page, same as GoTo action.


    Available click options (see puppeteer `page.click
    <https://pptr.dev/#?product=Puppeteer&version=v3.2.0&show=api-pageclickselector-options>`_):

    * ``button`` (str): ``left``, ``right``, or ``middle``, defaults to
      ``left``.
    * ``clickCount`` (int): defaults to 1.
    * ``delay`` (int|float): Time to wait between ``mousedown`` and
      ``mouseup`` in milliseconds. defaults to 0.

    Response for this action contains page state after click and wait.

    """

    endpoint = "click"

    def __init__(
        self,
        selector: str,
        click_options: dict = None,
        wait_options: dict = None,
        navigation_options: dict = None,
    ):
        self.selector = selector
        self.click_options = click_options
        self.wait_options = wait_options
        self.navigation_options = navigation_options

    def payload(self):
        return {
            "selector": self.selector,
            "clickOptions": self.click_options,
            "waitOptions": self.wait_options,
            "navigationOptions": self.navigation_options,
        }


class Scroll(PuppeteerServiceAction):
    """
    Scroll page down or for specific element.

    :param str selector: If provided, scroll this element into view, otherwise scroll down by window
        height.
    :param dict wait_options: Same as in GoTo and Click actions.

    Response for this action contains page state after scroll and wait.

    """

    endpoint = "scroll"

    def __init__(self, selector: str = None, wait_options: dict = None):
        self.selector = selector
        self.wait_options = wait_options

    def payload(self):
        return {"selector": self.selector, "waitOptions": self.wait_options}


class Screenshot(PuppeteerServiceAction):
    """
    Take a screenshot.

    Available options (see puppeteer `page.screenshot
    <https://pptr.dev/#?product=Puppeteer&version=v3.2.0&show=api-pagescreenshotoptions>`_)

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

    Response for this action contains screenshot image in base64 encoding.

    """

    endpoint = "screenshot"

    def __init__(self, options: dict = None, **kwargs):
        self.options = options or {}
        self.options.update(kwargs)

    def payload(self):
        return {"options": self.options}


class Har(PuppeteerServiceAction):
    """
    The `Har` action is used to capture and retrieve the HTTP Archive (HAR) file,
    which contains detailed information about network requests and responses
    made during the session.

    This action is called without any arguments. To generate the HAR file,
    you must pass the `har_recording=True` argument to `PuppeteerRequest`
    when initiating the request.
    """

    endpoint = "har"

    def payload(self):
        return {}


class FillForm(PuppeteerServiceAction):
    """
    Fill out and submit forms on a webpage.

    Available options:

    * ``input_mapping`` (dict): A dictionary where each key is a CSS selector, and
    each value is another dictionary containing details about the input for that element.
    Each entry in the dictionary should follow this structure:

    * ``selector`` (str): The CSS selector for the input element (used as the key).
    * ``value`` (str): The text to be inputted into the element.
    * ``delay`` (int, optional): A delay (in milliseconds) between each keystroke
        when inputting the text. Defaults to 0 if not provided.

    * ``submit_button`` (str, optional): The CSS selector for the form's submit button.
    If provided, the button will be clicked after filling in the form.
    """

    endpoint = "fill_form"

    def __init__(self, input_mapping: dict, submit_button: str = None):
        self.input_mapping = input_mapping
        self.submit_button = submit_button

    def payload(self):
        return {"inputMapping": self.input_mapping, "submitButton": self.submit_button}


class RecaptchaSolver(PuppeteerServiceAction):
    """
    Tries to solve recaptcha on the page.
    First it tries to find recaptcha. If it couldn't find a recaptcha nothing
    will happen to your 2captcha balance.
    Then it solves recaptcha with 2captcha service and inserts the special code
    into the page automatically.
    Note that it does not click buttons like "submit" buttons.

    :param bool solve_recaptcha: (default = True) enables automatic solving of recaptcha on the page if found.
            If false is provided recaptcha will still be detected on the page but not solved.
            You can get info about found recaptchas via return value.
    :param bool close_on_empty: (default = True) whether to close page or not if there was no captcha on the page.

    :param dict navigation_options: Navigation options, same as GoTo action.
    :param dict wait_options: Options specifying wait after navigation, same as GoTo action.

    Response for this action is PuppeteerRecaptchaSolverResponse.
    """

    endpoint = "recaptcha_solver"

    def __init__(
        self,
        solve_recaptcha: bool = True,
        close_on_empty: bool = False,
        navigation_options: dict = None,
        wait_options: dict = None,
        **kwargs,
    ):
        self.solve_recaptcha = solve_recaptcha
        self.close_on_empty = close_on_empty
        self.navigation_options = navigation_options
        self.wait_options = wait_options

    def payload(self):
        return {
            "solve_recaptcha": self.solve_recaptcha,
            "close_on_empty": self.close_on_empty,
            "navigationOptions": self.navigation_options,
            "waitOptions": self.wait_options,
        }


class CustomJsAction(PuppeteerServiceAction):
    """
    Evaluate custom JavaScript function on page.

    :param str js_action: JavaScript function.

    Expected signature: ``async function action(page, request)``.

    JavaScript function should not return object with attributes
    of ``scrapypuppeteer.PuppeteerJsonResponse``.
    Otherwise, undefined behaviour is possible.

    Response for this action contains result of the function.

    """

    endpoint = "action"
    content_type = "application/javascript"

    def __init__(self, js_action: str):
        self.js_action = js_action

    def payload(self):
        return self.js_action


class Compose(PuppeteerServiceAction):
    """
    Compose several scrapy-puppeteer actions into one action and send it to the service.

    Response for this action is PuppeteerResponse to last action in a sequence.

    """

    endpoint = "compose"

    def __init__(self, *actions: PuppeteerServiceAction):
        self.actions = self.__flatten(actions)

    @staticmethod
    def __flatten(
        actions: Tuple[PuppeteerServiceAction, ...],
    ) -> List[PuppeteerServiceAction]:
        flatten_actions = []
        for action in actions:
            if isinstance(action, Compose):
                flatten_actions.extend(action.actions)
            else:
                flatten_actions.append(action)
        if not flatten_actions:
            raise ValueError("No actions provided in `Compose`.")
        return flatten_actions

    def payload(self):
        return {
            "actions": [
                {"endpoint": action.endpoint, "body": action.payload()}
                for action in self.actions
            ]
        }
