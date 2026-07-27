from abc import ABC, abstractmethod

class AMTModel(ABC):
    @abstractmethod
    def transcribe(self, input_audio_path: str, output_midi_path: str):
        pass

def get_amt_model(model_type: str) -> "AMTModel":
    if model_type == "basic_pitch":
        from amt_basic_pitch import BasicPitchAMT
        return BasicPitchAMT()
    elif model_type == "transkun":
        from amt_transkun import TranskunAMT
        return TranskunAMT()
    else:
        raise ValueError(f"Model type {model_type} not recognized")