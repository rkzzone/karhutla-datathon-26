"""Bandingkan aturan label lama dan baru, lalu simpan label terkoreksi.

Skrip ini TIDAK memuat model dan TIDAK butuh GPU. Ia hanya membaca mask GT,
sehingga selesai di bawah satu menit. Jalankan ini LEBIH DULU sebelum
memutuskan apakah perlu melatih ulang.

Aturan lama (train.py:392, KELIRU):
    has_smoke = (gt > 60).any() and (gt < 190).any()
    Dua pemeriksaan TERPISAH atas seluruh citra. Begitu ada api, piksel api
    memenuhi syarat pertama dan piksel latar memenuhi syarat kedua, sehingga
    has_smoke selalu benar dan kelas fire_no_smoke tidak terjangkau.

Aturan baru (dataset_rffnet.py:129, BENAR):
    has_smoke = ((gt > 60) & (gt < 190)).any()
    Konjungsi PER PIKSEL, sama dengan yang dipakai saat pelatihan.

Keluaran:
    labels_terkoreksi.csv  -> split, frame_index, label_lama, label_baru
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import numpy as np
from PIL import Image

KELAS = ["no_fire", "fire_no_smoke", "fire_smoke"]


def label_baru(g: np.ndarray) -> int:
    api = bool((g >= 190).any())
    asap = bool(((g > 60) & (g < 190)).any())
    return 2 if (api and asap) else (1 if api else 0)


def label_lama(g: np.ndarray) -> int:
    api = bool((g >= 190).any())
    asap = bool((g > 60).any() and (g < 190).any())
    return 2 if (api and asap) else (1 if api else 0)


def baca_ids(rffnet_root: Path, split: str) -> list[str]:
    p = rffnet_root.parent / "lists" / f"{split}_flm.txt"
    ids = []
    for baris in open(p, encoding="utf-8"):
        m = re.search(r"\((\d+)\)", baris)
        if m:
            ids.append(m.group(1))
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rffnet-root", required=True,
                    help="folder FLAME2 milik RFFNet, berisi images/, sejajar dengan lists/")
    ap.add_argument("--splits", nargs="+", default=["train", "val", "test"])
    ap.add_argument("--image-size", type=int, default=224)
    ap.add_argument("--out", default="labels_terkoreksi.csv")
    args = ap.parse_args()

    root = Path(args.rffnet_root)
    img_dir = root / "images"
    baris_keluar = []

    for split in args.splits:
        baru = {0: 0, 1: 0, 2: 0}
        lama = {0: 0, 1: 0, 2: 0}
        beda = 0
        for fid in baca_ids(root, split):
            g = np.array(Image.open(img_dir / f"img_gt_({fid}).png").convert("L")
                         .resize((args.image_size, args.image_size), Image.NEAREST))
            b, l = label_baru(g), label_lama(g)
            baru[b] += 1
            lama[l] += 1
            beda += int(b != l)
            baris_keluar.append({"split": split, "frame_index": fid,
                                 "label_lama": l, "label_baru": b})
        fmt = lambda d: {KELAS[k]: v for k, v in d.items()}
        print(f"{split:6s} baru={fmt(baru)}  lama={fmt(lama)}  BERBEDA={beda}")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["split", "frame_index", "label_lama", "label_baru"])
        w.writeheader()
        w.writerows(baris_keluar)
    print(f"\n-> {args.out}  ({len(baris_keluar)} baris)")
    print("\nBila BERBEDA = 0 di seluruh split, seluruh angka lama sah apa adanya.")
    print("Bila bukan nol, jalankan 01_rehitung_dengan_label_terkoreksi.py.")


if __name__ == "__main__":
    main()
