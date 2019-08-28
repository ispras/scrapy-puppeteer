import asyncio
from twisted.internet import asyncioreactor

asyncioreactor.install(asyncio.get_event_loop())

from scrapy.cmdline import execute
execute(['scrapy', 'crawl', 'meduza'])
