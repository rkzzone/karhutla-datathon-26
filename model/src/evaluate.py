"""src/evaluate.py

Dua mode:
  --mode metrics      -> evaluasi penuh di suatu split RFFNet, pakai src/metrics.py,
                          simpan hasil ke JSON.
  --mode smoke_test    -> jalankan SATU inferensi, hasilkan JSON PERSIS bentuk
                          kontrak API (Bagian 3.4) -- ini yang wajib di-share ke
                          tim produk begitu Stage 2 selesai (Gerbang 2).

Pemakaian:
    python src/evaluate.py --checkpoint weights_final/fusion_v1.pth \\
        --rffnet-root /kaggle/input/.../FLAME2 --mode smoke_test \\
        --out reports/sample_output_stage2.json

    python src/evaluate.py --checkpoint weights_final/fusion_v2_gated.pth \\
        --rffnet-root /kaggle/input/.../FLAME2 --mode metrics --split test \\
        --out reports/eval_stage6_test.json
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.dataset_rffnet import RFFNetDataset
from src.models.encoder_rgb import RGBEncoder
from src.models.encoder_thermal import ThermalEncoder
from src.models.fusion_cross_attention import CrossAttentionFusion
from src.models.head_classification import ClassificationHead, CLASS_LABELS
from src.models.head_segmentation import SegmentationHead
from src.models.reliability_gate import DualReliabilityGate
from src import metrics as M


def load_model_components(checkpoint_path: str, device: torch.device, with_gate: bool = False,
                           with_segmentation: bool = False):
    ckpt = torch.load(checkpoint_path, map_location=device)

    rgb_encoder = RGBEncoder().to(device)
    thermal_encoder = ThermalEncoder().to(device)
    fusion = CrossAttentionFusion().to(device)
    head = ClassificationHead().to(device)
    rgb_encoder.load_state_dict(ckpt["rgb_encoder"])
    thermal_encoder.load_state_dict(ckpt["thermal_encoder"])
    fusion.load_state_dict(ckpt["fusion"])
    head.load_state_dict(ckpt["head_classification"])
    for m in (rgb_encoder, thermal_encoder, fusion, head):
        m.eval()

    gate = None
    if with_gate:
        gate = DualReliabilityGate().to(device)
        if "gate" in ckpt:
            gate.load_state_dict(ckpt["gate"])
            gate.eval()
        else:
            print("[evaluate] PERINGATAN: with_gate=True tapi checkpoint tidak punya "
                  "state 'gate' -- Stage 5 mungkin belum selesai, field modality_reliability "
                  "akan diisi 0.5/0.5.")
            gate = None

    seg_head = None
    if with_segmentation:
        seg_head = SegmentationHead().to(device)
        if "segmentation_head" in ckpt:
            seg_head.load_state_dict(ckpt["segmentation_head"])
            seg_head.eval()
        else:
            print("[evaluate] PERINGATAN: with_segmentation=True tapi checkpoint tidak "
                  "punya state 'segmentation_head' -- Stage 6 Jalur B mungkin belum selesai.")
            seg_head = None

    return rgb_encoder, thermal_encoder, fusion, head, gate, seg_head


def build_api_prediction(
    rgb_encoder, thermal_encoder, fusion, head, gate, seg_head,
    rgb_tensor: torch.Tensor, thermal_tensor: torch.Tensor, device: torch.device,
    source_trigger: str = "patrol_scheduled", lat: float = 0.0, lon: float = 0.0,
) -> dict:
    """Bangun SATU objek JSON PERSIS sesuai kontrak API Bagian 3.4, dari satu
    pasang tensor RGB+termal yang sudah dinormalisasi & di-batch (1, C, H, W)."""
    with torch.no_grad():
        r_tok = rgb_encoder(rgb_tensor.to(device))
        th_tok = thermal_encoder(thermal_tensor.to(device))

        if gate is not None:
            rgb_rel, thermal_rel = gate(r_tok, th_tok)
            fused = fusion(r_tok, th_tok, rgb_rel, thermal_rel)
            modality_reliability = {"rgb": round(rgb_rel.item(), 4), "thermal": round(thermal_rel.item(), 4)}
        else:
            fused = fusion(r_tok, th_tok)
            modality_reliability = {"rgb": 0.5, "thermal": 0.5}  # placeholder sebelum Stage 5 (Bagian 3.4)

        logits = head(fused)
        prediction = ClassificationHead.logits_to_api_prediction(logits)[0]

        if seg_head is not None:
            seg_logits = seg_head(fused)
            heatmap_bytes = SegmentationHead.logits_to_heatmap_png_bytes(seg_logits)
            import base64
            heatmap_path = "data:image/png;base64," + base64.b64encode(heatmap_bytes).decode("ascii")
            method = "segmentation_head"
        else:
            heatmap_path = ""  # placeholder sebelum Stage 6 (Bagian 3.4)
            method = "attention_rollout"  # default sebelum Jalur B tersedia

    return {
        "alert_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"lat": lat, "lon": lon},
        "prediction": prediction,
        "modality_reliability": modality_reliability,
        "localization": {"heatmap_path": heatmap_path, "method": method},
        "images": {"rgb_url": "", "thermal_url": ""},  # diisi tim produk saat integrasi (Stage 10)
        "source_trigger": source_trigger,
        "operator_decision": None,
    }


def run_smoke_test(args, device):
    """Jalankan satu inferensi dari sampel val (BUKAN test, per Bagian 3.8 #2 --
    smoke test bukan evaluasi final, tidak perlu pakai held-out set) dan simpan
    hasilnya PERSIS bentuk kontrak API."""
    dataset = RFFNetDataset("val", Path(args.rffnet_root), train=False, with_mask=False)
    rgb_t, thermal_t = dataset[0]

    rgb_encoder, thermal_encoder, fusion, head, gate, seg_head = load_model_components(
        args.checkpoint, device, with_gate=args.with_gate, with_segmentation=args.with_segmentation
    )
    result = build_api_prediction(
        rgb_encoder, thermal_encoder, fusion, head, gate, seg_head,
        rgb_t.unsqueeze(0), thermal_t.unsqueeze(0), device,
    )

    # validasi bentuk PERSIS sesuai kontrak sebelum disimpan -- kalau ini gagal,
    # JANGAN kirim ke tim produk, perbaiki dulu.
    required_top_keys = {"alert_id", "timestamp", "location", "prediction", "modality_reliability",
                          "localization", "images", "source_trigger", "operator_decision"}
    assert required_top_keys.issubset(result.keys()), (required_top_keys - result.keys())
    assert result["prediction"]["label"] in CLASS_LABELS
    print("[evaluate] Validasi kontrak API: OK, semua field wajib ada.")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[evaluate] Smoke test JSON disimpan ke {out_path}")
    print(json.dumps(result, indent=2))


def run_metrics_eval(args, device):
    """Evaluasi penuh (precision/recall/F1 klasifikasi, mIoU kalau ada segmentation
    head) di split yang diminta. PERINGATAN: kalau --split test, ini HARUS SEKALI
    SAJA per Bagian 3.8 #2 -- jangan panggil berulang untuk tuning."""
    dataset = RFFNetDataset(args.split, Path(args.rffnet_root), train=False, with_mask=True)
    rgb_encoder, thermal_encoder, fusion, head, gate, seg_head = load_model_components(
        args.checkpoint, device, with_gate=args.with_gate, with_segmentation=args.with_segmentation
    )

    y_true, y_pred = [], []
    per_sample_iou = []
    with torch.no_grad():
        for i in range(len(dataset)):
            rgb_t, thermal_t, seg, has_obj = dataset[i]
            rgb_b, thermal_b = rgb_t.unsqueeze(0).to(device), thermal_t.unsqueeze(0).to(device)
            r_tok, th_tok = rgb_encoder(rgb_b), thermal_encoder(thermal_b)
            if gate is not None:
                rgb_rel, thermal_rel = gate(r_tok, th_tok)
                fused = fusion(r_tok, th_tok, rgb_rel, thermal_rel)
            else:
                fused = fusion(r_tok, th_tok)

            logits = head(fused)
            pred_idx = logits.argmax(-1).item()
            has_fire, has_smoke = (seg == 2).any().item(), (seg == 1).any().item()
            true_idx = 2 if (has_fire and has_smoke) else (1 if has_fire else 0)
            y_true.append(true_idx)
            y_pred.append(pred_idx)

            if seg_head is not None:
                seg_logits = seg_head(fused)
                pred_mask = seg_logits.argmax(dim=1)[0].cpu()
                per_sample_iou.append(M.iou_per_class(pred_mask, seg, n_classes=3))

    cls_metrics = M.classification_precision_recall_f1(y_true, y_pred)
    result = {"split": args.split, "n_samples": len(dataset), "classification": cls_metrics}

    if per_sample_iou:
        miou, per_class_iou = M.mean_iou(per_sample_iou)
        result["segmentation"] = {"mIoU": miou, "per_class_iou": per_class_iou}

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[evaluate] Hasil metrik disimpan ke {out_path}")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Evaluasi model / smoke test kontrak API.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--rffnet-root", required=True)
    parser.add_argument("--mode", choices=["metrics", "smoke_test"], required=True)
    parser.add_argument("--split", choices=["train", "val", "test"], default="val",
                         help="WAJIB baca peringatan Bagian 3.8 #2 sebelum pakai 'test'")
    parser.add_argument("--with-gate", action="store_true", help="Muat reliability gate (Stage 5+)")
    parser.add_argument("--with-segmentation", action="store_true", help="Muat segmentation head (Stage 6+)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if args.mode == "smoke_test":
        run_smoke_test(args, device)
    else:
        if args.split == "test":
            print("[evaluate] PERINGATAN: kamu memanggil evaluasi di rffnet_test.csv. "
                  "Per Bagian 3.8 #2 ini HANYA boleh dilakukan SEKALI untuk laporan akhir. "
                  "Pastikan ini bukan run tuning berulang.")
        run_metrics_eval(args, device)


if __name__ == "__main__":
    main()
