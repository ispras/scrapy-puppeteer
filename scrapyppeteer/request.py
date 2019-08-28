from scrapy.http import Request


class PyppeteerRequest(Request):
    def __init__(self, action, context_id=None, page_id=None, close_context=False, **kwargs):
        kwargs['dont_filter'] = True

        meta = kwargs.get('meta', {})
        meta['dont_obey_robotstxt'] = True
        kwargs['meta'] = meta

        super().__init__('pptr://', **kwargs)
        self.action = action
        self.context_id = context_id
        self.page_id = page_id
        self.close_context = close_context
