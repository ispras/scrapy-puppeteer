from pytest import mark
from scrapypuppeteer.actions import GoTo, GoForward, GoBack, Click, Scroll
from itertools import product
from constants import URLS, NAV_OPTS, WAIT_OPTS, SELECTORS, CLICK_OPTS, HAR_RECORDING


def _gen_goto():
    for url, nav_opt, wait_opt, har_recording in product(URLS, NAV_OPTS, WAIT_OPTS, HAR_RECORDING):
        expected = {
            "url": url,
            "navigationOptions": nav_opt,
            "waitOptions": wait_opt,
            "harRecording": har_recording
        }
        yield url, nav_opt, wait_opt, har_recording, expected


def _gen_back_forward():
    for nav_opt, wait_opt in product(NAV_OPTS, WAIT_OPTS):
        expected = {
            "navigationOptions": nav_opt,
            "waitOptions": wait_opt,
        }
        yield nav_opt, wait_opt, expected


def _gen_click():
    for selector, click_opt, nav_opt, wait_opt in product(
        SELECTORS, CLICK_OPTS, NAV_OPTS, WAIT_OPTS
    ):
        expected = {
            "selector": selector,
            "clickOptions": click_opt,
            "waitOptions": wait_opt,
            "navigationOptions": nav_opt,
        }
        yield selector, click_opt, nav_opt, wait_opt, expected


def _gen_scroll():
    for selector, wait_opt in product(SELECTORS, WAIT_OPTS):
        expected = {"selector": selector, "waitOptions": wait_opt}
        yield selector, wait_opt, expected


@mark.parametrize("url, navigation_options, wait_options, expected", _gen_goto())
def test_goto(url, navigation_options, wait_options, har_recording, expected):
    action = GoTo(url, navigation_options, wait_options, har_recording)
    assert action.payload() == expected


@mark.parametrize("navigation_options, wait_options, expected", _gen_back_forward())
def test_go_forward(navigation_options, wait_options, expected):
    action = GoForward(navigation_options, wait_options)
    assert action.payload() == expected


@mark.parametrize("navigation_options, wait_options, expected", _gen_back_forward())
def test_go_forward(navigation_options, wait_options, expected):
    action = GoBack(navigation_options, wait_options)
    assert action.payload() == expected


@mark.parametrize(
    "selector, click_options, navigation_options, wait_options, expected", _gen_click()
)
def test_click(selector, click_options, navigation_options, wait_options, expected):
    action = Click(selector, click_options, wait_options, navigation_options)
    assert action.payload() == expected


@mark.parametrize("selector, wait_options, expected", _gen_scroll())
def test_scroll(selector, wait_options, expected):
    action = Scroll(selector, wait_options)
    assert action.payload() == expected
