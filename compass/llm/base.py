import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("compass.llm")


class LLM(ABC):
    def __init__(self, api_key, base_url, model_id):
        self.api_key = api_key
        self.base_url = base_url
        self.model_id = model_id
        self.is_executing = False

    @abstractmethod
    def standard_request(self, messages):
        pass

    @abstractmethod
    def streaming_request(self, messages):
        pass

    @abstractmethod
    def stock_message(self, message):
        pass
