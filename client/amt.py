from abc import ABC, abstractmethod

class AMTModel(ABC):

    @abstractmethod
    def transcribe(self, input_audio_path: str, output_midi_path: str):
        pass

    @staticmethod
    def create(model_type: str) -> "AMTModel":
        if model_type == "basic_pitch":
            from amt_basic_pitch import BasicPitchAMT
            return BasicPitchAMT()
        if model_type == "transkun":
            from amt_transkun import TranskunAMT
            return TranskunAMT()