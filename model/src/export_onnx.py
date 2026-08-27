"""src/export_onnx.py

Ekspor model fusi ke ONNX -- dipakai tim data untuk Stage 8b (edge_bench/01_export_onnx.py
memanggil/mengonsumsi file .onnx ini, atau logika di bawah bisa dipanggil langsung).

Model dibungkus jadi satu nn.Module (`FusionInferenceWrapper`) yang cuma menerima
2 input tensor (RGB, termal) dan mengeluarkan 1 output (logit klasifikasi) --
bentuk paling sederhana untuk benchmarking latensi/ukuran, TIDAK termasuk
reliability gate atau segmentation head (itu cabang opsional, diekspor terpisah
kalau tim data butuh, lihat --include-gate/--include-segmentation).

Pemakaian:
    python src/export_onnx.py --checkpoint weights_final/fusion_v2_gated.pth \\
        --out weights_final/fusion_v2.onnx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.encoder_rgb import RGBEncoder
from src.models.encoder_thermal import ThermalEncoder
from src.models.fusion_cross_attention import CrossAttentionFusion
from src.models.head_classification import ClassificationHead
from src.models.head_segmentation import SegmentationHead


class FusionInferenceWrapper(nn.Module):
    """Satu forward pass end-to-end: (RGB, termal) -> logit klasifikasi (+ opsional
    logit segmentasi). Tanpa modality dropout (nonaktif otomatis di eval mode) dan
    tanpa reliability gate (opsional, lihat include_gate)."""

    def __init__(self, rgb_encoder, thermal_encoder, fusion, head, seg_head=None):
        super().__init__()
        self.rgb_encoder = rgb_encoder
        self.thermal_encoder = thermal_encoder
        self.fusion = fusion
        self.head = head
        self.seg_head = seg_head

    def forward(self, rgb: torch.Tensor, thermal: torch.Tensor):
        r_tok = self.rgb_encoder(rgb)
        th_tok = self.thermal_encoder(thermal)
        fused = self.fusion(r_tok, th_tok)
        logits = self.head(fused)
        if self.seg_head is not None:
            seg_logits = self.seg_head(fused)
            return logits, seg_logits
        return logits


def build_wrapper(checkpoint_path: str, device: torch.device, include_segmentation: bool = False):
    ckpt = torch.load(checkpoint_path, map_location=device)

    rgb_encoder = RGBEncoder().to(device)
    thermal_encoder = ThermalEncoder().to(device)
    fusion = CrossAttentionFusion().to(device)
    head = ClassificationHead().to(device)
    rgb_encoder.load_state_dict(ckpt["rgb_encoder"])
    thermal_encoder.load_state_dict(ckpt["thermal_encoder"])
    fusion.load_state_dict(ckpt["fusion"])
    head.load_state_dict(ckpt["head_classification"])

    seg_head = None
    if include_segmentation:
        assert "segmentation_head" in ckpt, "Checkpoint tidak punya segmentation_head -- Stage 6 blm selesai"
        seg_head = SegmentationHead().to(device)
        seg_head.load_state_dict(ckpt["segmentation_head"])

    wrapper = FusionInferenceWrapper(rgb_encoder, thermal_encoder, fusion, head, seg_head)
    wrapper.eval()
    return wrapper


def export(args):
    """CATATAN PENTING -- batch size TETAP = 1, bukan dynamic:
    `align_token_grid` di fusion_cross_attention.py melakukan `.reshape(B, C, grid, grid)`
    eksplisit; di bawah tracer ONNX (dynamo), B ini ter-bake jadi konstanta sehingga
    model hasil ekspor GAGAL kalau diberi batch>1 saat inference (RuntimeError reshape
    di onnxruntime -- ditemukan & diverifikasi saat pengujian modul ini). Memperbaikinya
    butuh refactor align_token_grid supaya trace-safe (pakai -1 di reshape, bukan B
    hasil unpack shape) -- di luar scope referensi ini.

    Batch=1 TETAP merupakan pilihan yang benar untuk target deploy edge (Bagian 9
    catatan 9: latensi dihitung per-frame/per-ubin, bukan batch besar), jadi
    keterbatasan ini tidak menghalangi tujuan Stage 8. Kalau tim data butuh dynamic
    batch (mis. utk benchmark throughput), refactor align_token_grid dulu sebelum
    ekspor ulang.
    """
    device = torch.device("cpu")  # ekspor ONNX selalu dari CPU -- target deploy edge = CPU/mobile
    wrapper = build_wrapper(args.checkpoint, device, args.include_segmentation)

    dummy_rgb = torch.randn(1, 3, args.image_size, args.image_size)
    dummy_thermal = torch.randn(1, 1, args.image_size, args.image_size)

    output_names = ["classification_logits", "segmentation_logits"] if args.include_segmentation else ["classification_logits"]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        wrapper,
        (dummy_rgb, dummy_thermal),
        str(out_path),
        input_names=["rgb", "thermal"],
        output_names=output_names,
        opset_version=18,   # opset 17 memicu percobaan downgrade yg gagal di sebagian versi onnxscript -- 18 bersih
        # TIDAK ada dynamic_axes -- lihat catatan batch=1 di docstring atas
    )
    print(f"[export_onnx] Model diekspor ke {out_path} (batch TETAP=1, lihat catatan di export())")

    # Verifikasi ringan -- muat ulang lewat onnxruntime kalau tersedia, pastikan
    # inferensi jalan tanpa error sebelum diserahkan ke tim data.
    try:
        import onnxruntime as ort
        import numpy as np
        session = ort.InferenceSession(str(out_path))
        outputs = session.run(None, {
            "rgb": dummy_rgb.numpy().astype(np.float32),
            "thermal": dummy_thermal.numpy().astype(np.float32),
        })
        print(f"[export_onnx] Verifikasi onnxruntime OK -- {len(outputs)} output, "
              f"shape: {[o.shape for o in outputs]}")
    except ImportError:
        print("[export_onnx] onnxruntime tidak terpasang -- verifikasi dilewati. "
              "Install `onnxruntime` utk verifikasi otomatis (lihat requirements.txt).")


def main():
    parser = argparse.ArgumentParser(description="Ekspor model fusi ke ONNX untuk edge benchmarking (Stage 8b).")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--include-segmentation", action="store_true",
                         help="Sertakan segmentation head (Stage 6+) di graph ONNX")
    args = parser.parse_args()
    export(args)


if __name__ == "__main__":
    main()
