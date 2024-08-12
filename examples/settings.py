BOT_NAME = "scrapypuppeteer"

SPIDER_MODULES = ["examples.spiders"]
NEWSPIDER_MODULE = "examples.spiders"

CONCURRENT_REQUESTS = 1

DOWNLOADER_MIDDLEWARES = {
    "scrapypuppeteer.middleware.PuppeteerServiceDownloaderMiddleware": 1042
}

PUPPETEER_SERVICE_URL = "http://localhost:3000"

PUPPETEER_LOCAL = False