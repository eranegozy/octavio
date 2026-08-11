# TODO: was written in part by Claude Code

import logging
import os
import types

import pkg_resources
import torch
import moduleconf
import soxr

from amt import AMTModel

from transkun.transcribe import readAudio
from transkun.Data import writeMidi
from transkun import CRF

TK_REQUIRED_KEYS = {
    'TRANSCRIPTION_PARAMS.AMT_PARAMS.transkun.device', 'TRANSCRIPTION_PARAMS.AMT_PARAMS.transkun.weight_path', 'TRANSCRIPTION_PARAMS.AMT_PARAMS.transkun.conf_path'
}

DEFAULT_ONNX_PATH = os.path.join(os.path.dirname(__file__), "transkun_backbone_scorer.int8.onnx")

os.nice(15) # lower priority

class TranskunAMT(AMTModel):
    def __init__(self, device="cpu", weight_path=None, conf_path=None):
        weight_path = weight_path or pkg_resources.resource_filename("transkun", "pretrained/2.0.pt")
        conf_path = conf_path or pkg_resources.resource_filename("transkun", "pretrained/2.0.conf")

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


def _ort_process_frames_batch(self, framesBatch):
    """Drop-in replacement for TransKun.processFramesBatch (see
    transkun/ModelTransformer.py) that runs the backbone+scorer on ONNX Runtime
    instead of torch. Everything before/after that split (gain norm, mel
    frontend, CRF construction) is copied verbatim from the original."""
    nBatch = framesBatch.shape[0]

    framesBatchMean = torch.mean(framesBatch, dim=[1, 2, 3], keepdim=True)
    framesBatchStd = torch.std(framesBatch, dim=[1, 2, 3], keepdim=True)
    framesBatch = (framesBatch - framesBatchMean) / (framesBatchStd + 1e-8)

    featuresBatch = self.framewiseFeatureExtractor(framesBatch).contiguous()
    nChannel = 1
    featuresBatch = featuresBatch.view(nBatch * nChannel, *featuresBatch.shape[-3:])

    device = featuresBatch.device
    ort_inputs = {"featuresBatch": featuresBatch.detach().cpu().numpy()}
    ctx_np, S_batch_np, S_skip_np = self._ort_session.run(None, ort_inputs)

    ctx = torch.from_numpy(ctx_np).to(device)
    S_batch = torch.from_numpy(S_batch_np).to(device)
    S_skip_batch = torch.from_numpy(S_skip_np).to(device)

    S_batch = S_batch.flatten(-2, -1)
    S_skip_batch = S_skip_batch.flatten(-2, -1)

    crf = CRF.NeuralSemiCRFInterval(S_batch, S_skip_batch)
    return crf, ctx


# Transkun with the backbone+scorer (the expensive transformer stack) swapped
# for a quantized ONNX Runtime graph exported via export_transkun_onnx.py. The
# mel frontend, semi-CRF decode, and attribute heads stay in torch/transkun
# unmodified -- they're cheap and not the bottleneck being optimized here.
class TranskunOnnxAMT(AMTModel):
    def __init__(self, device="cpu", weight_path=None, conf_path=None, onnx_path=None,
                 intra_op_num_threads=None):
        weight_path = weight_path or pkg_resources.resource_filename("transkun", "pretrained/2.0.pt")
        conf_path = conf_path or pkg_resources.resource_filename("transkun", "pretrained/2.0.conf")
        onnx_path = onnx_path or DEFAULT_ONNX_PATH
        if not os.path.exists(onnx_path):
            raise FileNotFoundError(
                f"{onnx_path} not found. Run export_transkun_onnx.py on a machine with "
                "the full transkun/torch stack installed and copy the resulting "
                "*.int8.onnx file here first."
            )

        conf_manager = moduleconf.parseFromFile(conf_path)
        transkun = conf_manager["Model"].module.TransKun
        conf = conf_manager["Model"].config

        checkpoint = torch.load(weight_path, map_location=device)
        model = transkun(conf=conf).to(device)

        key = "best_state_dict" if "best_state_dict" in checkpoint else "state_dict"
        model.load_state_dict(checkpoint[key], strict=False)
        model.eval()

        import onnxruntime as ort
        sess_options = ort.SessionOptions()
        if intra_op_num_threads:
            sess_options.intra_op_num_threads = intra_op_num_threads

        # backbone+scorer are superseded by the ONNX session; drop the fp32
        # weights so they don't sit around in memory unused
        del model.backbone
        del model.scorer

        model._ort_session = ort.InferenceSession(
            onnx_path, sess_options=sess_options, providers=["CPUExecutionProvider"]
        )
        model.processFramesBatch = types.MethodType(_ort_process_frames_batch, model)

        self.model = model

    def transcribe(self, input_audio_path, output_midi_path, device="cpu"):
        fs, audio = readAudio(input_audio_path)
        if fs != self.model.fs:
            logging.warning(f"Sampling rate mismatch between audio {input_audio_path} and Transkun AMT Model, ")
            audio = soxr.resample(audio, fs, self.model.fs)
        x = torch.from_numpy(audio).to(device)
        notes_estimate = self.model.transcribe(x, discardSecondHalf=False)
        writeMidi(notes_estimate).write(output_midi_path)


# Transkun but with linear layer weights set to INT8 precision
class TranskunInt8AMT(AMTModel):
    def __init__(self, device="cpu", weight_path=None, conf_path=None):
        weight_path = weight_path or pkg_resources.resource_filename("transkun", "pretrained/2.0.pt")
        conf_path = conf_path or pkg_resources.resource_filename("transkun", "pretrained/2.0.conf")

        conf_manager = moduleconf.parseFromFile(conf_path)
        transkun = conf_manager["Model"].module.TransKun
        conf = conf_manager["Model"].config

        checkpoint = torch.load(weight_path, map_location=device)
        model = transkun(conf=conf).to(device)

        key = "best_state_dict" if "best_state_dict" in checkpoint else "state_dict"
        model.load_state_dict(checkpoint[key], strict=False)

        model.eval()

        # these submodules read `.weight.device` as a plain tensor attribute in their
        # forward(), which breaks if nn.Linear is swapped for a quantized module
        POS_EMBED_NAMES = [
            "backbone.posEmbedBuilder",
            "backbone.posEmbedBuilderAttnTF",
            "backbone.posEmbedBuilderAttnTE",
        ]
        modules_by_name = dict(model.named_modules())
        original_projs = {name: modules_by_name[name].proj for name in POS_EMBED_NAMES}

        torch.backends.quantized.engine = 'qnnpack'
        model = torch.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)

        quantized_by_name = dict(model.named_modules())
        for name, proj in original_projs.items():
            quantized_by_name[name].proj = proj

        self.model = model

        self.model = model

    def transcribe(self, input_audio_path, output_midi_path, device="cpu"):
        fs, audio = readAudio(input_audio_path)
        if fs != self.model.fs:
            logging.warning(f"Sampling rate mismatch between audio {input_audio_path} and Transkun AMT Model, ")
            audio = soxr.resample(audio, fs, self.model.fs)
        x = torch.from_numpy(audio).to(device)
        notes_estimate = self.model.transcribe(x, discardSecondHalf=False)
        writeMidi(notes_estimate).write(output_midi_path)