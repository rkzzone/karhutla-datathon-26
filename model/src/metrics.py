"""src/metrics.py

SATU-SATUNYA implementasi metrik untuk seluruh proyek.
Semua skrip -- train.py, evaluate.py, notebook mana pun, termasuk skrip evaluasi
Tim data -- WAJIB memanggil fungsi dari sini. Jangan menulis ulang definisi metrik
di tempat lain.

Definisi lengkap tiap metrik ada di Lampiran C concept paper. Ringkasan:
  - precision / recall / F1        -> klasifikasi & deteksi (di IoU tertentu)
  - IoU / mIoU                     -> segmentasi piksel
  - mAP@0.5, mAP@[0.5:0.95]        -> deteksi/localization berbasis bbox
  - delta_m (ketahanan modalitas)  -> M(fusi penuh) - M(modalitas m saja)
  - latency_stats                  -> median dari >=100 pengukuran setelah warm-up
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np
import torch


# =============================================================================
# Klasifikasi (Stage 1: 3 kelas -- fire_smoke | fire_no_smoke | no_fire)
# =============================================================================

CLASS_LABELS = ["no_fire", "fire_no_smoke", "fire_smoke"]  # index 0,1,2 -- urutan tetap, dipakai di semua tempat


def classification_precision_recall_f1(
    y_true: Sequence[int], y_pred: Sequence[int], n_classes: int = len(CLASS_LABELS)
) -> Dict[str, Dict[str, float]]:
    """Precision/recall/F1 per kelas + macro-average, format multi-kelas (bukan biner).

    Return: {"per_class": {label: {precision, recall, f1, support}}, "macro": {...}}
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    assert y_true.shape == y_pred.shape, "y_true dan y_pred harus sama panjang"

    per_class = {}
    precisions, recalls, f1s = [], [], []
    for c in range(n_classes):
        tp = int(np.sum((y_pred == c) & (y_true == c)))
        fp = int(np.sum((y_pred == c) & (y_true != c)))
        fn = int(np.sum((y_pred != c) & (y_true == c)))
        support = int(np.sum(y_true == c))
        precision = tp / (tp + fp + 1e-9)
        recall = tp / (tp + fn + 1e-9)
        f1 = 2 * precision * recall / (precision + recall + 1e-9)
        label = CLASS_LABELS[c] if c < len(CLASS_LABELS) else str(c)
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)

    macro = {
        "precision": float(np.mean(precisions)),
        "recall": float(np.mean(recalls)),
        "f1": float(np.mean(f1s)),
    }
    return {"per_class": per_class, "macro": macro}


# =============================================================================
# Segmentasi (Stage 6 Jalur B: head segmentasi)
# =============================================================================

def iou_per_class(pred_mask: torch.Tensor, gt_mask: torch.Tensor, n_classes: int) -> Dict[int, float]:
    """IoU per kelas untuk SATU pasang mask (H, W) label diskrit (bukan one-hot).
    Dipanggil berulang lalu di-agregasi lewat mean_iou() untuk dapat mIoU dataset."""
    result = {}
    for c in range(n_classes):
        pred_c = pred_mask == c
        gt_c = gt_mask == c
        intersection = (pred_c & gt_c).sum().item()
        union = (pred_c | gt_c).sum().item()
        result[c] = intersection / union if union > 0 else float("nan")
    return result


def mean_iou(per_sample_iou: List[Dict[int, float]]) -> Tuple[float, Dict[int, float]]:
    """Agregasi IoU per-kelas dari banyak sampel -> mIoU keseluruhan + IoU rata-rata per kelas.
    NaN (kelas tidak muncul di sampel itu) diabaikan dari rata-rata, bukan dihitung 0."""
    n_classes = max(d.keys() for d in per_sample_iou) if per_sample_iou else []
    n_classes = max((max(d.keys()) for d in per_sample_iou), default=-1) + 1
    per_class_values: Dict[int, List[float]] = {c: [] for c in range(n_classes)}
    for d in per_sample_iou:
        for c, v in d.items():
            if not np.isnan(v):
                per_class_values[c].append(v)
    per_class_mean = {c: (float(np.mean(v)) if v else float("nan")) for c, v in per_class_values.items()}
    valid = [v for v in per_class_mean.values() if not np.isnan(v)]
    miou = float(np.mean(valid)) if valid else float("nan")
    return miou, per_class_mean


# =============================================================================
# Deteksi / Localization berbasis bbox (Stage 6 evaluasi, dipakai juga notebook
# deteksi terpisah)
# =============================================================================

def iou_xywh(box1: Tuple[float, float, float, float], box2: Tuple[float, float, float, float]) -> float:
    """IoU dua box format (x, y, w, h), x/y pojok kiri-atas."""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    xa, ya = max(x1, x2), max(y1, y2)
    xb, yb = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
    inter = max(0.0, xb - xa) * max(0.0, yb - ya)
    union = w1 * h1 + w2 * h2 - inter
    return inter / union if union > 0 else 0.0


def average_precision(
    preds_by_score: List[Tuple[int, float, float, float, float, float]],
    gt_boxes_by_image: Dict[int, List[Tuple[float, float, float, float]]],
    iou_threshold: float = 0.5,
) -> float:
    """AP gaya VOC (precision envelope + integrasi trapesium manual -- TIDAK pakai
    np.trapz, karena dihapus di NumPy 2.x, diganti np.trapezoid; manual di sini
    supaya tidak gantung ke versi NumPy).

    preds_by_score: list (image_id, score, x, y, w, h) -- SATU kelas.
    gt_boxes_by_image: {image_id: [(x,y,w,h), ...]} -- kelas yang sama.
    """
    preds_sorted = sorted(preds_by_score, key=lambda p: -p[1])
    n_gt = sum(len(v) for v in gt_boxes_by_image.values())
    if n_gt == 0:
        return 0.0

    matched = {img_id: [False] * len(boxes) for img_id, boxes in gt_boxes_by_image.items()}
    tp = np.zeros(len(preds_sorted))
    fp = np.zeros(len(preds_sorted))

    for i, (img_id, score, x, y, w, h) in enumerate(preds_sorted):
        gts = gt_boxes_by_image.get(img_id, [])
        best_iou, best_j = 0.0, -1
        for j, gt_box in enumerate(gts):
            if matched[img_id][j]:
                continue
            iou = iou_xywh((x, y, w, h), gt_box)
            if iou > best_iou:
                best_iou, best_j = iou, j
        if best_iou >= iou_threshold and best_j >= 0:
            tp[i] = 1
            matched[img_id][best_j] = True
        else:
            fp[i] = 1

    tp_cum, fp_cum = np.cumsum(tp), np.cumsum(fp)
    recall = tp_cum / n_gt
    precision = tp_cum / np.maximum(tp_cum + fp_cum, 1e-9)

    for i in range(len(precision) - 2, -1, -1):
        precision[i] = max(precision[i], precision[i + 1])
    recall = np.concatenate([[0.0], recall, [1.0]])
    precision = np.concatenate([[precision[0] if len(precision) else 0.0], precision, [0.0]])
    ap = sum((recall[i + 1] - recall[i]) * precision[i + 1] for i in range(len(recall) - 1))
    return float(ap)


def map_at_thresholds(
    preds_by_class: Dict[int, List[Tuple[int, float, float, float, float, float]]],
    gt_by_class: Dict[int, Dict[int, List[Tuple[float, float, float, float]]]],
    iou_thresholds: Sequence[float],
) -> Dict[str, float]:
    """mAP@0.5 (iou_thresholds=[0.5]) dan mAP@[0.5:0.95] (iou_thresholds=np.arange(0.5,1.0,0.05)).
    Return {"mAP@0.5": ..., "mAP@[0.5:0.95]": ...} -- baca kunci sesuai thresholds yg dikirim."""
    per_threshold = []
    for thr in iou_thresholds:
        aps = [
            average_precision(preds_by_class.get(c, []), gt_by_class.get(c, {}), iou_threshold=thr)
            for c in gt_by_class
        ]
        per_threshold.append(float(np.mean(aps)) if aps else 0.0)

    result = {}
    if len(iou_thresholds) == 1:
        result[f"mAP@{iou_thresholds[0]}"] = per_threshold[0]
    else:
        result["mAP@[0.5:0.95]"] = float(np.mean(per_threshold))
    return result


# =============================================================================
# Ketahanan modalitas: delta_m = M(fusi penuh) - M(modalitas m saja)
# =============================================================================

def delta_m(metric_fusion: float, metric_unimodal: float) -> float:
    """Selisih ketahanan modalitas (Bagian 3.5). Makin kecil delta_m -> makin tahan
    model saat modalitas m hilang. Dipakai di Ablation #1 dan #2 (gating)."""
    return metric_fusion - metric_unimodal


# =============================================================================
# Latensi: median dari >=100 pengukuran setelah warm-up (Bagian 3.5, catatan 9)
# =============================================================================

@dataclass
class LatencyStats:
    median_ms: float
    p90_ms: float
    p99_ms: float
    mean_ms: float
    n_measurements: int
    warmup_discarded: int


def measure_latency(
    fn: Callable[[], None],
    n_measurements: int = 100,
    n_warmup: int = 10,
    device_sync: Callable[[], None] | None = None,
) -> LatencyStats:
    """Ukur latensi satu fungsi (mis. satu forward pass / satu panggilan inference
    end-to-end). WAJIB >=100 pengukuran setelah warm-up (Bagian 3.5).

    device_sync: panggil torch.cuda.synchronize kalau fn jalan di GPU, supaya
    pengukuran tidak salah krn eksekusi CUDA asinkron.
    """
    for _ in range(n_warmup):
        fn()
        if device_sync:
            device_sync()

    timings_ms = []
    for _ in range(n_measurements):
        t0 = time.perf_counter()
        fn()
        if device_sync:
            device_sync()
        timings_ms.append((time.perf_counter() - t0) * 1000)

    arr = np.array(timings_ms)
    return LatencyStats(
        median_ms=float(np.median(arr)),
        p90_ms=float(np.percentile(arr, 90)),
        p99_ms=float(np.percentile(arr, 99)),
        mean_ms=float(np.mean(arr)),
        n_measurements=n_measurements,
        warmup_discarded=n_warmup,
    )


# =============================================================================
# Non-Max Suppression -- utilitas pendukung deteksi (dipanggil sebelum evaluasi
# mAP dan sebelum decode heatmap jadi bbox final)
# =============================================================================

def nms(boxes: List[Tuple[int, float, float, float, float, float]], iou_threshold: float = 0.4) -> List[Tuple]:
    """boxes: list (cls_id, x, y, w, h, score). NMS per kelas."""
    keep = []
    for cls_id in set(b[0] for b in boxes):
        cls_boxes = sorted([b for b in boxes if b[0] == cls_id], key=lambda b: -b[5])
        while cls_boxes:
            best = cls_boxes.pop(0)
            keep.append(best)
            cls_boxes = [b for b in cls_boxes if iou_xywh(best[1:5], b[1:5]) < iou_threshold]
    return keep


if __name__ == "__main__":
    # Sanity check ringan -- jalankan `python src/metrics.py` buat verifikasi cepat
    # tanpa perlu data/model asli.
    y_true = [0, 0, 1, 1, 2, 2, 2]
    y_pred = [0, 1, 1, 1, 2, 2, 0]
    print("Tes klasifikasi:", classification_precision_recall_f1(y_true, y_pred))

    assert abs(iou_xywh((0, 0, 10, 10), (0, 0, 10, 10)) - 1.0) < 1e-6
    assert iou_xywh((0, 0, 10, 10), (100, 100, 5, 5)) == 0.0
    print("Tes IoU: OK")

    gt = {0: [(10, 10, 20, 20)]}
    preds = [(0, 0.9, 10, 10, 20, 20)]
    ap = average_precision(preds, gt, iou_threshold=0.5)
    assert abs(ap - 1.0) < 1e-6, ap
    print("Tes AP (prediksi sempurna): OK, AP =", ap)

    stats = measure_latency(lambda: sum(range(1000)), n_measurements=20, n_warmup=5)
    print("Tes latency_stats:", stats)

    print("\nSemua sanity check src/metrics.py LOLOS.")
