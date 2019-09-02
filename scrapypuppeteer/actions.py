class Goto:
    def __init__(self, url: str, options: dict = None, **kwargs):
        self.url = url
        self.options = options or {}
        self.options.update(kwargs)
