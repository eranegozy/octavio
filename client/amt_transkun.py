import transkun.transcribe as tk

class TranskunAMT(AMTModel):
    def transcribe(self, input_audio_path, output_midi_path):
        raise NotImplementedError