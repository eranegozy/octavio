# TODO: was written by Claude Code

"""
One-off export of Transkun's backbone+scorer to ONNX, then int8-quantized
via onnxruntime.

Only the backbone (transformer encoder) and scorer (ScaledInnerProductIntervalScorer)
are exported -- this is the expensive linear/attention-heavy compute identified in
transkun/ModelTransformer.py:TransKun.processFramesBatch. The mel frontend, semi-CRF
Viterbi decode, and velocity/timing heads stay in PyTorch (transkun package) since
they're cheap and not worth quantizing.

Run this on a machine with the full transkun + torch stack installed (not
necessarily the Pi). Copy the resulting *.int8.onnx file to the Pi and point
TranskunOnnxAMT's onnx_path at it.

    python3.10 export_transkun_onnx.py --out ./transkun_backbone_scorer.onnx \
        --quantized-out ./transkun_backbone_scorer.int8.onnx
"""

import argparse
import contextlib
import math

import pkg_resources
import torch
import torch.nn as nn
import torch.nn.functional as F
import moduleconf
from onnxruntime.quantization import quantize_dynamic, QuantType
from onnxruntime.quantization.shape_inference import quant_pre_process

from transkun.Util import makeFrame


def _sdpa_rank_agnostic(query, key, value, attn_mask=None, dropout_p=0.0,
                         is_causal=False, scale=None):
    """Manual matmul+softmax equivalent of F.scaled_dot_product_attention.

    transkun's attention (transkun/LayersTransformer.py:184) calls SDPA on 5D
    tensors -- an extra batch-like axis alongside [batch, heads, seq, head_dim]
    for its factorized F/T attention. The exporter's SDPA lowering only
    supports rank-4 q/k/v, so this stand-in (algebraically identical for the
    no-mask, non-causal case transkun actually uses) is traced instead.
    """
    assert attn_mask is None and not is_causal, "transkun only calls SDPA with plain (q, k, v)"
    if scale is None:
        scale = query.shape[-1] ** -0.5
    attn = torch.matmul(query, key.transpose(-2, -1)) * scale
    attn = torch.softmax(attn, dim=-1)
    return torch.matmul(attn, value)


@contextlib.contextmanager
def patch_sdpa_for_export():
    original = F.scaled_dot_product_attention
    F.scaled_dot_product_attention = _sdpa_rank_agnostic
    try:
        yield
    finally:
        F.scaled_dot_product_attention = original


class BackboneScorerWrapper(nn.Module):
    """Wraps TransKun.backbone + TransKun.scorer, the split point between
    'expensive neural forward pass' and 'CRF decode' in processFramesBatch."""

    def __init__(self, model):
        super().__init__()
        assert model.useInnerProductScorer, (
            "this export wrapper only covers the inner-product scorer branch "
            "used by pretrained/2.0.pt; adjust if using a different checkpoint"
        )
        self.backbone = model.backbone
        # avoid tracing through torch.utils.checkpoint.checkpoint during export
        self.backbone.useGradientCheckpoint = False
        self.scorer = model.scorer
        self.register_buffer(
            "output_indices", torch.tensor(model.targetMIDIPitch, dtype=torch.long)
        )

    def forward(self, features_batch):
        ctx = self.backbone(features_batch, outputIndices=self.output_indices)
        s, s_skip = self.scorer(ctx)
        return ctx, s, s_skip


def make_dummy_features(model):
    """Build a real (not random-shaped) featuresBatch the same way
    TransKun.processFramesBatch does, sized to exactly what transcribe() always
    feeds it: transcribe() pads/truncates every segment to a fixed
    segmentSize before framing (see ModelTransformer.py:769), so nStep is a
    deterministic constant, not actually dynamic -- export a static-shape
    graph and sidestep dynamic-shape ONNX export/inference issues entirely.
    """
    segment_size = math.ceil(model.segmentSizeInSecond * model.fs)
    dummy_audio = torch.randn(1, segment_size)  # [nChannel=1 (mono), nSample]
    frames = makeFrame(dummy_audio, model.hopSize, model.windowSize)
    frames_batch = frames.unsqueeze(0)  # [nBatch=1, nChannel, nFrame, windowSize]

    with torch.no_grad():
        frames_batch_mean = torch.mean(frames_batch, dim=[1, 2, 3], keepdim=True)
        frames_batch_std = torch.std(frames_batch, dim=[1, 2, 3], keepdim=True)
        frames_batch = (frames_batch - frames_batch_mean) / (frames_batch_std + 1e-8)
        features_batch = model.framewiseFeatureExtractor(frames_batch).contiguous()
        n_batch = frames_batch.shape[0]
        features_batch = features_batch.view(n_batch * 1, *features_batch.shape[-3:])

    return features_batch


def load_model(weight_path, conf_path):
    weight_path = weight_path or pkg_resources.resource_filename("transkun", "pretrained/2.0.pt")
    conf_path = conf_path or pkg_resources.resource_filename("transkun", "pretrained/2.0.conf")

    conf_manager = moduleconf.parseFromFile(conf_path)
    transkun_cls = conf_manager["Model"].module.TransKun
    conf = conf_manager["Model"].config

    checkpoint = torch.load(weight_path, map_location="cpu")
    model = transkun_cls(conf=conf)
    key = "best_state_dict" if "best_state_dict" in checkpoint else "state_dict"
    model.load_state_dict(checkpoint[key], strict=False)
    model.eval()
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weight-path", default=None)
    parser.add_argument("--conf-path", default=None)
    parser.add_argument("--out", default="transkun_backbone_scorer.onnx")
    parser.add_argument("--quantized-out", default="transkun_backbone_scorer.int8.onnx")
    parser.add_argument(
        "--legacy-exporter", action="store_true",
        help="use the older TorchScript-based exporter (dynamo=False) instead of the "
             "default dynamo exporter, which can be more permissive about custom ops",
    )
    parser.add_argument(
        "--opset", type=int, default=17,
        help="target ONNX opset. The dynamo exporter traces at a newer opset internally "
             "and downgrades to this target via onnxscript's version converter, which can "
             "fail on ops like Pad; try --legacy-exporter first, or bump this if it persists",
    )
    args = parser.parse_args()

    model = load_model(args.weight_path, args.conf_path)
    wrapper = BackboneScorerWrapper(model)
    wrapper.eval()

    dummy = make_dummy_features(model)
    print(f"Exporting with fixed featuresBatch shape {tuple(dummy.shape)} "
          f"(segmentSizeInSecond={model.segmentSizeInSecond}, fs={model.fs}, "
          f"hopSize={model.hopSize}, windowSize={model.windowSize})")

    with patch_sdpa_for_export():
        torch.onnx.export(
            wrapper,
            (dummy,),
            args.out,
            input_names=["featuresBatch"],
            output_names=["ctx", "S", "S_skip"],
            opset_version=args.opset,
            dynamo=not args.legacy_exporter,
        )
    print(f"Exported fp32 ONNX graph to {args.out}")

    # onnxruntime's own (more robust) shape inference, run before quantization
    # as onnxruntime.quantization itself recommends -- raw onnx.shape_inference
    # can spuriously fail on this backbone's reshape/position-embedding pattern
    preprocessed_path = args.out.removesuffix(".onnx") + ".preprocessed.onnx"
    try:
        quant_pre_process(args.out, preprocessed_path, skip_symbolic_shape=False)
    except Exception as e:
        print(f"quant_pre_process with symbolic shape inference failed ({e}); retrying with skip_symbolic_shape=True")
        quant_pre_process(args.out, preprocessed_path, skip_symbolic_shape=True)
    print(f"Pre-processed graph for quantization at {preprocessed_path}")

    quantize_dynamic(
        model_input=preprocessed_path,
        model_output=args.quantized_out,
        weight_type=QuantType.QUInt8,
        per_channel=True,
    )
    print(f"Quantized int8 ONNX graph to {args.quantized_out}")


if __name__ == "__main__":
    main()
