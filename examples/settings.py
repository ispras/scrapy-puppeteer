BOT_NAME = 'scrapyppeteer'

SPIDER_MODULES = ['examples.spiders']
NEWSPIDER_MODULE = 'examples.spiders'

DOWNLOAD_HANDLERS = {
    'pptr': 'scrapyppeteer.PyppeteerDownloadHandler'
}

PYPPETEER_SETTINGS = {
    'headless': False,
    'dontClose': True
}

CONCURRENT_REQUESTS = 1
