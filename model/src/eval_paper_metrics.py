"""src/eval_paper_metrics.py

Satu skrip sekali-jalan untuk melengkapi angka yang dibutuhkan paper semifinal.
Menutup tiga celah sekaligus:

  1. Ablation #1 DIULANG dengan perbaikan bug: di `train_stage2()`, modul
     `modality_dropout` tidak pernah dipindah ke mode eval (train.py:283-296
     memanggil .eval() pada rgb_encoder/thermal_encoder/fusion/head saja), padahal
     nn.Module default training=True. Akibatnya baris `fusi_penuh` di
     reports/ablation1_unimodal_vs_fusion.csv dihitung DENGAN modality dropout
     p=0.2 masih aktif secara acak. Di sini seluruh modul dipaksa .eval().

  2. Evaluasi klasifikasi pada SPLIT UJI (rffnet_test.csv, 200 pasangan) -- sejauh
     ini semua angka klasifikasi berasal dari split validasi.

  3. Metrik selain akurasi: precision/recall/F1 per kelas, macro-average, matriks
     konfusi, dan distribusi kelas. Semua memakai src/metrics.py (satu-satunya
     implementasi metrik).

Bonus yang tidak diminta tapi murah dan berguna: keluaran PER-SAMPEL disimpan ke
CSV, sehingga uji McNemar berpasangan (fusi vs unimodal) bisa dihitung penulis
paper. Tanpa ini, perbandingan hanya bisa memakai CI binomial tak-berpasangan
yang jauh lebih lemah.

Harness sengaja meniru run_stage4() PERSIS (muat PIL mentah -> degradasi di ruang
piksel 0-255 -> normalisasi resmi), bukan DataLoader + PairedAugment seperti
Stage 2, supaya angkanya bisa dibandingkan langsung dengan kurva degradasi.

Jalankan (di Kaggle, tempat datanya berada):

    python src/eval_paper_metrics.py \
        --checkpoint weights_final/fusion_v1.pth \
        --rffnet-root /kaggle/input/datasets/abangbuan/flame2/FLAME2 \
        --splits val test \
        --out-dir reports/

Catatan: RGBEncoder memuat DINOv2 lewat torch.hub -- butuh internet aktif di
notebook Kaggle, atau cache torch.hub yang sudah terisi.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torchvision import transforms as T

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import metrics as M
from src.data.dataset_rffnet import (RGB_MEAN, RGB_STD, THERMAL_MEAN, THERMAL_STD,
                                     parse_split_list)
from src.models.encoder_rgb import RGBEncoder
from src.models.encoder_thermal import ThermalEncoder
from src.models.fusion_cross_attention import CrossAttentionFusion
from src.models.head_classification import ClassificationHead, CLASS_LABELS
from src.models.modality_dropout import ModalityDropout
from src.augmentation.smoke_synthesis import inject_synthetic_smoke
from src.augmentation.thermal_degradation import degrade_thermal

MODES = [("fusi_penuh", None), ("rgb_saja", "thermal"), ("termal_saja", "rgb")]


def label_from_gt(gt_arr: np.ndarray) -> int:
    """Label 3-kelas dari mask GT RFFNet. 0=no_fire, 1=fire_no_smoke, 2=fire_smoke.

    Konjungsi asap dihitung PER PIKSEL, sesuai dataset_rffnet.py:129 dan collate
    Stage 2 yang dipakai saat PELATIHAN:
        seg_target[(gt_arr > 60) & (gt_arr < 190)] = 1

    Ini berbeda dari run_stage4()/train_stage5() di train.py:392, yang memakai dua
    `.any()` terpisah: `(gt_arr > 60).any() and (gt_arr < 190).any()`. Bentuk itu
    selalu benar begitu ada api (piksel api memenuhi syarat pertama, piksel latar
    memenuhi syarat kedua), sehingga kelas 1 tidak terjangkau secara konstruksi.
    """
    has_fire = bool((gt_arr >= 190).any())
    has_smoke = bool(((gt_arr > 60) & (gt_arr < 190)).any())
    return 2 if (has_fire and has_smoke) else (1 if has_fire else 0)


def label_from_gt_versi_lama(gt_arr: np.ndarray) -> int:
    """Aturan keliru yang dipakai run_stage4()/train_stage5(). Dipertahankan HANYA
    untuk mengukur selisih dampaknya, jangan dipakai menilai model."""
    has_fire = bool((gt_arr >= 190).any())
    has_smoke = bool((gt_arr > 60).any() and (gt_arr < 190).any())
    return 2 if (has_fire and has_smoke) else (1 if has_fire else 0)


def build_model(checkpoint: Path, device: torch.device):
    rgb_encoder = RGBEncoder().to(device)
    thermal_encoder = ThermalEncoder().to(device)
    fusion = CrossAttentionFusion().to(device)
    head = ClassificationHead().to(device)

    ckpt = torch.load(checkpoint, map_location=device)
    rgb_encoder.load_state_dict(ckpt["rgb_encoder"])
    thermal_encoder.load_state_dict(ckpt["thermal_encoder"])
    fusion.load_state_dict(ckpt["fusion"])
    head.load_state_dict(ckpt["head_classification"])

    # p diambil dari checkpoint kalau ada; nilainya tidak berpengaruh karena
    # modul dipaksa .eval() -- disertakan supaya jejaknya terekam di JSON.
    p = float(ckpt.get("modality_dropout_p", 0.2))
    modality_dropout = ModalityDropout(p).to(device)

    # === PERBAIKAN BUG: SEMUA modul ke eval, termasuk modality_dropout ===
    for mod in (rgb_encoder, thermal_encoder, fusion, head, modality_dropout):
        mod.eval()
    assert not modality_dropout.training, "modality_dropout masih di mode train"

    return rgb_encoder, thermal_encoder, fusion, head, modality_dropout, p


@torch.no_grad()
def evaluate_split(split: str, rffnet_root: Path, tau: float, model, device,
                   image_size: int = 224):
    rgb_encoder, thermal_encoder, fusion, head, _, _ = model
    ids = parse_split_list(rffnet_root.parent / "lists" / f"{split}_flm.txt")
    img_dir = rffnet_root / "images"
    rgb_norm = T.Normalize(RGB_MEAN, RGB_STD)
    thermal_norm = T.Normalize(THERMAL_MEAN, THERMAL_STD)

    y_true: list[int] = []
    y_true_lama: list[int] = []   # diagnostik: label menurut aturan keliru Stage 4/5
    preds: dict[str, list[int]] = {name: [] for name, _ in MODES}
    confs: dict[str, list[float]] = {name: [] for name, _ in MODES}
    frame_ids: list[str] = []

    for i, fid in enumerate(ids):
        rgb_img = Image.open(img_dir / f"img_rgb_({fid}).png").convert("RGB").resize((image_size, image_size))
        thermal_img = Image.open(img_dir / f"img_ir_({fid}).png").convert("L").resize((image_size, image_size))
        gt_img = Image.open(img_dir / f"img_gt_({fid}).png").convert("L").resize((image_size, image_size), Image.NEAREST)

        rgb_np = np.array(rgb_img, dtype=np.uint8)
        thermal_np = np.array(thermal_img, dtype=np.uint8)

        # seed 42+i -- sama persis dengan run_stage4(), supaya tau>0 sebanding
        rgb_np = inject_synthetic_smoke(rgb_np, tau=tau, seed=42 + i)
        thermal_np = degrade_thermal(thermal_np, tau=tau, seed=42 + i)

        rgb_b = rgb_norm(torch.from_numpy(rgb_np / 255.0).permute(2, 0, 1).float()).unsqueeze(0).to(device)
        thermal_b = thermal_norm(torch.from_numpy(thermal_np / 255.0).unsqueeze(0).float()).unsqueeze(0).to(device)

        gt_arr = np.array(gt_img)
        y_true.append(label_from_gt(gt_arr))
        y_true_lama.append(label_from_gt_versi_lama(gt_arr))
        frame_ids.append(fid)

        for mode_name, force_drop in MODES:
            r_tok, th_tok = rgb_encoder(rgb_b), thermal_encoder(thermal_b)
            if force_drop == "rgb":
                r_tok = torch.zeros_like(r_tok)
            elif force_drop == "thermal":
                th_tok = torch.zeros_like(th_tok)
            logits = head(fusion(r_tok, th_tok))
            prob = torch.softmax(logits, dim=-1)
            conf, idx = prob.max(dim=-1)
            preds[mode_name].append(int(idx.item()))
            confs[mode_name].append(round(float(conf.item()), 6))

    return frame_ids, y_true, preds, confs, y_true_lama


def confusion_matrix(y_true, y_pred, n_classes=3):
    cm = [[0] * n_classes for _ in range(n_classes)]
    for t, p in zip(y_true, y_pred):
        cm[t][p] += 1
    return cm


def summarise(split: str, y_true, preds, confs, tau: float, checkpoint: str, p: float,
              y_true_lama=None):
    n = len(y_true)
    dist = {CLASS_LABELS[c]: int(sum(1 for t in y_true if t == c)) for c in range(3)}
    n_fire_or_smoke = int(sum(1 for t in y_true if t != 0))

    out = {
        "split": split,
        "n": n,
        "tau": tau,
        "checkpoint": checkpoint,
        "modality_dropout_p_di_checkpoint": p,
        "catatan_harness": ("muat PIL mentah -> degradasi 0-255 -> normalisasi; "
                            "modality_dropout dipaksa .eval() (perbaikan bug train.py:288)"),
        "distribusi_kelas": dist,
        "n_sampel_ber_api_atau_asap": n_fire_or_smoke,
        "per_mode": {},
    }

    # Diagnostik: seberapa besar dampak bug label train.py:392 (dua .any() terpisah).
    if y_true_lama is not None:
        beda = [i for i, (a, b) in enumerate(zip(y_true, y_true_lama)) if a != b]
        out["diagnostik_label"] = {
            "distribusi_aturan_lama": {CLASS_LABELS[c]: int(sum(1 for t in y_true_lama if t == c))
                                       for c in range(3)},
            "n_sampel_berbeda_label": len(beda),
            "persen_berbeda": round(100 * len(beda) / n, 2),
            "keterangan": ("aturan_lama = run_stage4()/train_stage5() train.py:392; "
                           "aturan_baru = per-piksel, sesuai label pelatihan Stage 2"),
        }
    for mode_name, _ in MODES:
        y_pred = preds[mode_name]
        prf = M.classification_precision_recall_f1(y_true, y_pred, n_classes=3)
        acc = sum(int(t == pr) for t, pr in zip(y_true, y_pred)) / n
        out["per_mode"][mode_name] = {
            "accuracy": acc,
            "n_benar": sum(int(t == pr) for t, pr in zip(y_true, y_pred)),
            "per_class": prf["per_class"],
            "macro": prf["macro"],
            "confusion_matrix": confusion_matrix(y_true, y_pred),
            "confusion_matrix_urutan_kelas": CLASS_LABELS,
            "confidence_rata2": float(np.mean(confs[mode_name])),
        }
    fus = out["per_mode"]["fusi_penuh"]["accuracy"]
    for mode_name, _ in MODES[1:]:
        out["per_mode"][mode_name]["delta_m_vs_fusion"] = M.delta_m(
            fus, out["per_mode"][mode_name]["accuracy"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default="weights_final/fusion_v1.pth")
    ap.add_argument("--rffnet-root", required=True,
                    help="folder FLAME2 milik RFFNet (berisi images/, sejajar dengan lists/)")
    ap.add_argument("--splits", nargs="+", default=["val", "test"])
    ap.add_argument("--tau", nargs="+", type=float, default=[0.0],
                    help="satu nilai, atau beberapa untuk menyapu kurva degradasi "
                         "(mis. --tau 0.0 0.2 0.4 0.6 0.8 1.0)")
    ap.add_argument("--image-size", type=int, default=224)
    ap.add_argument("--out-dir", default="reports")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[eval_paper_metrics] device={device}  checkpoint={args.checkpoint}")
    model = build_model(Path(args.checkpoint), device)
    p = model[5]
    print(f"[eval_paper_metrics] modality_dropout p={p} -- DIPAKSA eval, tidak aktif")

    taus = sorted(args.tau)
    sapu = len(taus) > 1  # mode sapuan kurva degradasi
    ringkasan = {}
    kurva: dict[str, list[dict]] = {}

    for split in args.splits:
        if split == "test":
            print("[eval_paper_metrics] PERINGATAN: menyentuh split TEST. Per Bagian 3.8 #2 "
                  "ini hanya boleh untuk laporan akhir, bukan tuning berulang.")
        kurva[split] = []

        for tau in taus:
            print(f"[eval_paper_metrics] evaluasi split={split} tau={tau} ...")
            frame_ids, y_true, preds, confs, y_true_lama = evaluate_split(
                split, Path(args.rffnet_root), tau, model, device, args.image_size)

            # nama kunci/berkas tetap kompatibel-mundur saat hanya satu tau
            suffix = f"_tau{tau}" if sapu else ""
            kunci = f"{split}{suffix}"
            ringkasan[kunci] = summarise(split, y_true, preds, confs, tau,
                                         args.checkpoint, p, y_true_lama)

            # keluaran per-sampel -> bahan uji McNemar berpasangan
            per_sample = out_dir / f"per_sample_predictions_{split}{suffix}.csv"
            with open(per_sample, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["frame_index", "label_true"]
                           + [f"pred_{m}" for m, _ in MODES]
                           + [f"conf_{m}" for m, _ in MODES])
                for i, fid in enumerate(frame_ids):
                    w.writerow([fid, y_true[i]]
                               + [preds[m][i] for m, _ in MODES]
                               + [confs[m][i] for m, _ in MODES])
            print(f"[eval_paper_metrics]   -> {per_sample}")

            s = ringkasan[kunci]
            print(f"   distribusi kelas: {s['distribusi_kelas']}  "
                  f"(ber-api/asap: {s['n_sampel_ber_api_atau_asap']})")
            dl = s.get("diagnostik_label")
            if dl:
                print(f"   [label] aturan lama: {dl['distribusi_aturan_lama']}  "
                      f"-> berbeda pada {dl['n_sampel_berbeda_label']} sampel "
                      f"({dl['persen_berbeda']}%)")
            for m, _ in MODES:
                r = s["per_mode"][m]
                print(f"   {m:12s} acc={r['accuracy']:.4f} ({r['n_benar']}/{s['n']})  "
                      f"macro-F1={r['macro']['f1']:.4f}")

            kurva[split].append({
                "tau": tau,
                "acc_rgb_only": s["per_mode"]["rgb_saja"]["accuracy"],
                "acc_thermal_only": s["per_mode"]["termal_saja"]["accuracy"],
                "acc_fusion": s["per_mode"]["fusi_penuh"]["accuracy"],
            })

        # CSV berformat SAMA PERSIS dengan reports/degradation_curve.csv Stage 4,
        # supaya kurva val (lama) dan kurva test (baru) bisa disandingkan langsung.
        if sapu:
            curve_csv = out_dir / f"degradation_curve_{split}.csv"
            with open(curve_csv, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["tau", "acc_rgb_only",
                                                  "acc_thermal_only", "acc_fusion"])
                w.writeheader()
                w.writerows(kurva[split])
            print(f"[eval_paper_metrics] -> {curve_csv}")

    json_path = out_dir / "paper_metrics.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(ringkasan, f, indent=2, ensure_ascii=False)
    print(f"[eval_paper_metrics] -> {json_path}")

    # Ablation #1 versi diperbaiki, skema kolom SAMA dengan file lama supaya
    # bisa dibandingkan berdampingan di paper. Hanya bermakna pada tau=0.
    kunci_val_bersih = next((k for k in ("val", "val_tau0.0") if k in ringkasan), None)
    if kunci_val_bersih:
        fixed = out_dir / "ablation1_unimodal_vs_fusion_FIXED.csv"
        s = ringkasan[kunci_val_bersih]
        with open(fixed, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["mode", "accuracy", "delta_m_vs_fusion"])
            for m, _ in MODES:
                r = s["per_mode"][m]
                w.writerow([m, r["accuracy"], r.get("delta_m_vs_fusion", "")])
        print(f"[eval_paper_metrics] -> {fixed}")

    print("\nSelesai. Kirim ke penulis paper: paper_metrics.json, "
          "ablation1_unimodal_vs_fusion_FIXED.csv, per_sample_predictions_*.csv")


if __name__ == "__main__":
    main()
