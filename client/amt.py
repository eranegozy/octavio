from abc import ABC, abstractmethod

class AMTModel(ABC):
    @abstractmethod
    def __init__(self):
        pass
    @abstractmethod
    def transcribe(self, in_filename, out_filename):
        pass