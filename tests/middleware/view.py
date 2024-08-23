import scrapy
from scrapy import Request


class ViewSpider(scrapy.Spider):
  name = "view"

  start_urls = ["https://www.google.com/recaptcha/api2/demo"]

  custom_settings = {}

  def start_requests(self):
    for url in self.start_urls:
      yield Request(url, callback=self.parse, errback=self.errback)

  def parse(self, response, **kwargs):
    self.log("WE ARE PARSING RESPONSE!")
    self.log(response)
    self.log(response.body)
    self.log("WE HAVE PARSED RESPONSE!")

  def errback(self, failure):
    self.log("We are in error processing!")
    self.log(failure)
