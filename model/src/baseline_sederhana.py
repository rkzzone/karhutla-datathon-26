"""src/baseline_sederhana.py

Baseline non-pembelajaran-mendalam untuk menguji apakah tolok ukur RFFNet/FLAME 2
benar-benar menuntut model fusi, atau sebenarnya dapat diselesaikan oleh aturan
sepele. Ini menjawab rubrik 6a ("baseline") dengan cara yang paling informatif
justru KARENA tugasnya jenuh: kalau satu ambang skalar sudah mencapai akurasi
setara model 31 juta parameter, maka akurasi bersih tidak bisa dipakai
mendukung klaim arsitektur apa pun -- dan itu temuan, bukan kegagalan.

Empat baseline:
  1. kelas_mayoritas   -- selalu prediksi kelas terbanyak di TRAIN
  2. ambang_termal     -- satu ambang pada rerata intensitas citra termal
  3. ambang_rgb        -- satu ambang pada rerata luminans citra RGB
  4. ambang_termal_maks-- satu ambang pada intensitas termal maksimum

Ambang dipilih HANYA di split train (menyapu seluruh nilai kandidat, ambil yang
memaksimalkan akurasi train), lalu diterapkan apa adanya ke val dan test. Tidak
ada penyetelan di val/test.

Tidak butuh torch, DINOv2, maupun GPU -- hanya PIL + numpy, selesai dalam hitungan
detik. Label diturunkan dari mask GT dengan aturan IDENTIK dengan train.py.

Jalankan:

    python src/baseline_sederhana.py \
        --rffnet-root /kaggle/input/datasets/abangbuan/flame2/FLAME2 \
        --out-dir reports/
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.dataset_rffnet import parse_split_list

CLASS_LABELS = ["no_fire", "fire_no_smoke", "fire_smoke"]


def label_from_gt(gt_arr: np.ndarray) -> int:
    """Sama persis dengan eval_paper_metrics.py: konjungsi asap PER PIKSEL,
    sesuai label yang dipakai saat pelatihan (dataset_rffnet.py:129)."""
    has_fire = bool((gt_arr >= 190).any())
    has_smoke = bool(((gt_arr > 60) & (gt_arr < 190)).any())
    return 2 if (has_fire and has_smoke) else (1 if has_fire else 0)


def muat_fitur(split: str, rffnet_root: Path, image_size: int = 224):
    """Kembalikan (frame_ids, y, fitur) dengan fitur = dict nama -> array (N,)."""
    ids = parse_split_list(rffnet_root.parent / "lists" / f"{split}_flm.txt")
    img_dir = rffnet_root / "images"

    fid_ok, y, f_th_mean, f_th_max, f_rgb_mean = [], [], [], [], []
    for fid in ids:
        rgb = np.array(Image.open(img_dir / f"img_rgb_({fid}).png").convert("L")
                       .resize((image_size, image_size)), dtype=np.float32)
        th = np.array(Image.open(img_dir / f"img_ir_({fid}).png").convert("L")
                      .resize((image_size, image_size)), dtype=np.float32)
        gt = np.array(Image.open(img_dir / f"img_gt_({fid}).png").convert("L")
                      .resize((image_size, image_size), Image.NEAREST))

        fid_ok.append(fid)
        y.append(label_from_gt(gt))
        f_th_mean.append(float(th.mean()))
        f_th_max.append(float(th.max()))
        f_rgb_mean.append(float(rgb.mean()))

    return (fid_ok, np.array(y),
            {"ambang_termal": np.array(f_th_mean),
             "ambang_termal_maks": np.array(f_th_max),
             "ambang_rgb": np.array(f_rgb_mean)})


def pilih_ambang(x: np.ndarray, y_biner: np.ndarray):
    """Sapu seluruh ambang kandidat, kembalikan (ambang, arah, akurasi_train).

    arah = +1 berarti 'x >= ambang -> positif (ada api)', -1 sebaliknya.
    Kandidat = titik tengah antar nilai unik yang berurutan.
    """
    nilai = np.unique(x)
    kandidat = ((nilai[:-1] + nilai[1:]) / 2) if len(nilai) > 1 else nilai
    terbaik = (None, 1, -1.0)
    for t in kandidat:
        for arah in (1, -1):
            pred = ((x >= t) if arah == 1 else (x < t)).astype(int)
            acc = float((pred == y_biner).mean())
            if acc > terbaik[2]:
                terbaik = (float(t), arah, acc)
    return terbaik


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rffnet-root", required=True)
    ap.add_argument("--splits", nargs="+", default=["train", "val", "test"])
    ap.add_argument("--image-size", type=int, default=224)
    ap.add_argument("--out-dir", default="reports")
    args = ap.parse_args()

    root = Path(args.rffnet_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = {}
    for split in args.splits:
        print(f"[baseline] memuat {split} ...")
        data[split] = muat_fitur(split, root, args.image_size)
        ids, y, _ = data[split]
        dist = {CLASS_LABELS[c]: int((y == c).sum()) for c in range(3)}
        print(f"           n={len(y)}  {dist}")

    if "train" not in data:
        raise SystemExit("Split 'train' wajib ada -- ambang dipilih di sana.")

    _, y_tr, f_tr = data["train"]
    # Tugas de facto biner: kelas 1 (fire_no_smoke) tidak pernah muncul.
    biner = lambda y: (y != 0).astype(int)
    kelas_mayoritas = int(np.bincount(y_tr, minlength=3).argmax())
    print(f"\n[baseline] kelas mayoritas di train = {CLASS_LABELS[kelas_mayoritas]}")

    aturan = {}
    for nama, x in f_tr.items():
        t, arah, acc = pilih_ambang(x, biner(y_tr))
        aturan[nama] = {"ambang": t, "arah": arah, "akurasi_train": acc}
        tanda = ">=" if arah == 1 else "<"
        print(f"[baseline] {nama:20s}: prediksi 'ada api' bila fitur {tanda} {t:.3f}  "
              f"(akurasi train {acc:.4f})")

    hasil = {"kelas_mayoritas_train": CLASS_LABELS[kelas_mayoritas],
             "aturan_ambang": aturan, "per_split": {}}

    for split in args.splits:
        ids, y, f = data[split]
        n = len(y)
        yb = biner(y)
        baris = {}

        pred_may = np.full(n, kelas_mayoritas)
        baris["kelas_mayoritas"] = {"accuracy": float((pred_may == y).mean()), "n": n}

        prediksi_semua = {"kelas_mayoritas": pred_may}
        for nama, x in f.items():
            a = aturan[nama]
            pos = (x >= a["ambang"]) if a["arah"] == 1 else (x < a["ambang"])
            # kelas positif dipetakan ke fire_smoke (2), negatif ke no_fire (0)
            pred = np.where(pos, 2, 0)
            prediksi_semua[nama] = pred
            fn = int(((yb == 1) & (~pos)).sum())
            fp = int(((yb == 0) & pos).sum())
            baris[nama] = {"accuracy": float((pred == y).mean()), "n": n,
                           "false_negative_api_terlewat": fn,
                           "false_positive_alarm_palsu": fp}

        hasil["per_split"][split] = baris
        print(f"\n=== {split} (n={n}) ===")
        for nama, r in baris.items():
            tambahan = ""
            if "false_negative_api_terlewat" in r:
                tambahan = (f"  FN={r['false_negative_api_terlewat']}"
                            f" FP={r['false_positive_alarm_palsu']}")
            print(f"  {nama:20s} acc={r['accuracy']:.4f}{tambahan}")

        # per-sampel -> supaya bisa di-McNemar-kan lawan model
        p = out_dir / f"per_sample_baseline_{split}.csv"
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            nama_baseline = list(prediksi_semua.keys())
            w.writerow(["frame_index", "label_true"] + [f"pred_{b}" for b in nama_baseline])
            for i, fid in enumerate(ids):
                w.writerow([fid, int(y[i])] + [int(prediksi_semua[b][i]) for b in nama_baseline])
        print(f"  -> {p}")

    jp = out_dir / "baseline_sederhana.json"
    json.dump(hasil, open(jp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\n-> {jp}")


if __name__ == "__main__":
    main()
