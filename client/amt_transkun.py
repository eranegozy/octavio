from amt import AMTModel

import pkg_resources
import torch
import moduleconf
import soxr

import logging

from transkun.transcribe import readAudio
from transkun.Data import writeMidi

TK_REQUIRED_KEYS = {
    'TRANSCRIPTION_PARAMS.AMT_PARAMS.transkun.device', 'TRANSCRIPTION_PARAMS.AMT_PARAMS.transkun.weight_path', 'TRANSCRIPTION_PARAMS.AMT_PARAMS.transkun.conf_path'
}

class TranskunAMT(AMTModel):
    # TODO: TEST IF THIS WORKS
    def __init__(self, device="cpu", weight_path=None, conf_path=None):
        weight_path = weight_path or pkg_resources.resource_filename("transkun", "pretrained/2.0.pt")
        conf_path = conf_path or pkg_resources.resource_filename("transkun", "pretrained/2.0.pt")

        conf_manager = moduleconf.parseFromFile(conf_path)
        transkun = conf_manager["Model"].module.TransKun
        conf = conf_manager["Model"].config

        checkpoint = torch.load(weight_path, map_location=device)
        model = transkun(conf=conf).to(device)

        key = "best_state_dict" if "best_state_dict" in checkpoint else "state_dict"
        model.load_state_dict(checkpoint[key], strict=False)
        model.eval()

        self.model = model

    def transcribe(self, input_audio_path, output_midi_path, device="cpu"):
        fs, audio = readAudio(input_audio_path)
        if fs != self.model.fs:
            logging.warning(f"Sampling rate mismatch between audio {input_audio_path} and Transkun AMT Model, ")
            audio = soxr.resample(audio, fs, self.model.fs)
        x = torch.from_numpy(audio).to(device)
        notes_estimate = self.model.transcribe(x, discardSecondHalf=False)
        writeMidi(notes_estimate).write(output_midi_path)