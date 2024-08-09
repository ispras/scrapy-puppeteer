__all__ = ["BrowserManager"]

from abc import ABC, abstractmethod

class BrowserManager(ABC):
    @abstractmethod
    def process_request(self, request, spider):
        pass
    
    @abstractmethod
    def close_used_contexts(self):
        pass

    @abstractmethod
    def process_response(self, middleware, request, response, spider):
        pass