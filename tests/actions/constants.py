from random import randint
from itertools import combinations

URLS = ("https://some_url.com", "not_url/not_url")
WAIT_UNTIL = ("load", "domcontentloaded", "networkidle0")
WAIT_OPTS = [None]
SELECTORS = ("nothing", "tr.td::attr(something)")
CLICK_OPTS = [None]


def __gen_nav_opts():
    options = [None]
    for opt_num in range(1, 5):
        for comb in combinations(WAIT_UNTIL, opt_num):
            timeout = randint(0, 100) * 1000
            options.append(
                {
                    "timeout": timeout,
                    "waitUntil": list(comb),
                }
            )
    return options


NAV_OPTS = __gen_nav_opts()
