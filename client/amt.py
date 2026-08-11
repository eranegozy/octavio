from abc import ABC, abstractmethod

class AMTModel(ABC):
    @abstractmethod
    def transcribe(self, input_audio_path: str, output_midi_path: str):
        pass

def get_amt_model(model_type: str) -> "AMTModel":
    if model_type == "basic-pitch":
        from amt_basic_pitch import BasicPitchAMT
        return BasicPitchAMT()
    elif model_type == "transkun":
        from amt_transkun import TranskunAMT
        return TranskunAMT()
    elif model_type == "transkun-int8":
        from amt_transkun import TranskunInt8AMT
        return TranskunInt8AMT()
    elif model_type == "transkun-onnx":
        from amt_transkun import TranskunOnnxAMT
        return TranskunOnnxAMT()
    else:
        raise ValueError(f"Model type {model_type} not recognized")