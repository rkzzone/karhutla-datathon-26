"""src/data/dataset_rffnet.py

Dataset loader untuk anotasi RFFNet (995 pasangan FLAME2 teranotasi mask, MIT license --
lihat Bagian 3.7). Dipakai di Stage 2 (fine-tune fusi), Stage 5 (gating), Stage 6
(head segmentasi Jalur B).

ATURAN KERAS #2 -- disiplin split uji:
`rffnet_test.csv` (200 sampel) HANYA disentuh untuk evaluasi final Stage 6, SEKALI.
Kelas ini tidak melarang penggunaan test split secara teknis (itu tanggung jawab
pemanggil skrip), tapi setiap fungsi di sini yang membentuk split "test" mencetak
peringatan supaya penyalahgunaan (dipakai berulang utk tuning) sulit tidak sengaja.

Struktur file (path relatif terhadap `root`, sesuai repo RoboFireFuseNet):
  {root}/FLAME2/images/img_rgb_(ID).png
  {root}/FLAME2/images/img_ir_(ID).png
  {root}/FLAME2/images/img_gt_(ID).png     -- mask 3-kelas: 0=bg, 125=asap, 255=api
  {root}/lists/{split}_flm.txt             -- daftar ID resmi per split
"""
from __future__ import annotations

import random
import re
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms as T

RGB_MEAN, RGB_STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
THERMAL_MEAN, THERMAL_STD = [0.5], [0.5]  # TODO-VERIFIKASI: statistik asli kalau sudah dihitung

MASK_CLASSES = {0: "background", 125: "smoke", 255: "fire"}
N_SEG_CLASSES = len(MASK_CLASSES)


def parse_split_list(list_path: Path) -> List[str]:
    """Baca lists/{split}_flm.txt -> list ID (angka dalam kurung, mis. 'img_rgb_(4267).png' -> '4267')."""
    ids = []
    with open(list_path, encoding="utf-8") as f:
        for line in f:
            m = re.search(r"\((\d+)\)", line)
            if m:
                ids.append(m.group(1))
    return ids


def mask_to_bboxes(mask_arr: np.ndarray, min_area: int = 9) -> List[Tuple[int, int, int, int, int]]:
    """Turunkan bbox dari mask -- 1 box per komponen terhubung. Dipakai kalau ada
    kebutuhan bbox (mis. notebook deteksi terpisah), TIDAK dipakai head segmentasi
    langsung (segmentasi pakai mask utuh sbg target)."""
    boxes = []
    for val, cls_id in [(125, 1), (255, 2)]:  # 1=asap, 2=api
        binary = (mask_arr == val).astype(np.uint8) * 255
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if cv2.contourArea(cnt) < min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            boxes.append((cls_id, x, y, w, h))
    return boxes


class PairedAugment:
    """Augmentasi geometris identik di RGB, termal, DAN mask (kalau ada) -- ketiganya
    harus tetap align spasial setelah transform."""

    def __init__(self, train: bool, image_size: int = 224):
        self.train = train
        self.image_size = image_size

    def __call__(self, rgb_img: Image.Image, thermal_img: Image.Image, gt_img: Image.Image | None = None):
        if self.train:
            if random.random() < 0.5:
                rgb_img = rgb_img.transpose(Image.FLIP_LEFT_RIGHT)
                thermal_img = thermal_img.transpose(Image.FLIP_LEFT_RIGHT)
                if gt_img is not None:
                    gt_img = gt_img.transpose(Image.FLIP_LEFT_RIGHT)
            angle = random.uniform(-10, 10)
            rgb_img = rgb_img.rotate(angle)
            thermal_img = thermal_img.rotate(angle)
            if gt_img is not None:
                gt_img = gt_img.rotate(angle, fillcolor=0)
        rgb_img = rgb_img.resize((self.image_size, self.image_size))
        thermal_img = thermal_img.resize((self.image_size, self.image_size))
        if gt_img is not None:
            gt_img = gt_img.resize((self.image_size, self.image_size), Image.NEAREST)
        return rgb_img, thermal_img, gt_img


class RFFNetDataset(Dataset):
    """RGB+termal(+mask opsional) dari split resmi RFFNet.

    `with_mask=True`  -> Stage 6 Jalur B (head segmentasi), target = mask 3-kelas
    `with_mask=False` -> Stage 2/5 (fusi/gating), kalau cuma butuh RGB+termal+label
                          klasifikasi turunan dari mask (ada objek fire/smoke atau tidak)
    """

    def __init__(self, split: str, root: Path, train: bool, with_mask: bool = True, image_size: int = 224):
        assert split in ("train", "val", "test")
        if split == "test":
            print("[dataset_rffnet] PERINGATAN: membentuk split 'test' (rffnet_test.csv, 200 "
                  "sampel). Per Bagian 3.8 #2, ini HANYA boleh dipakai SEKALI untuk evaluasi "
                  "final Stage 6 -- jangan dipanggil berulang untuk tuning.")
        self.split = split
        self.img_dir = root / "images"
        self.ids = parse_split_list(root.parent / "lists" / f"{split}_flm.txt")
        self.with_mask = with_mask
        self.augment = PairedAugment(train, image_size)
        self.rgb_norm = T.Compose([T.ToTensor(), T.Normalize(RGB_MEAN, RGB_STD)])
        self.thermal_norm = T.Compose([T.ToTensor(), T.Normalize(THERMAL_MEAN, THERMAL_STD)])

    def __len__(self) -> int:
        return len(self.ids)

    def __getitem__(self, idx: int):
        fid = self.ids[idx]
        rgb = Image.open(self.img_dir / f"img_rgb_({fid}).png").convert("RGB")
        thermal = Image.open(self.img_dir / f"img_ir_({fid}).png").convert("L")

        if self.with_mask:
            gt = Image.open(self.img_dir / f"img_gt_({fid}).png").convert("L")
            rgb, thermal, gt = self.augment(rgb, thermal, gt)
            gt_arr = np.array(gt)
            seg_target = np.zeros_like(gt_arr, dtype=np.int64)
            seg_target[(gt_arr > 60) & (gt_arr < 190)] = 1  # asap (~125)
            seg_target[gt_arr >= 190] = 2                    # api (~255)
            seg_target = torch.from_numpy(seg_target)
            has_object = int(seg_target.max().item() > 0)
            rgb_t, thermal_t = self.rgb_norm(rgb), self.thermal_norm(thermal)
            return rgb_t, thermal_t, seg_target, has_object
        else:
            rgb, thermal, _ = self.augment(rgb, thermal, None)
            rgb_t, thermal_t = self.rgb_norm(rgb), self.thermal_norm(thermal)
            return rgb_t, thermal_t


def build_rffnet_datasets(root: Path, with_mask: bool = True, image_size: int = 224):
    """Entry point utama -- bangun train/val/test dataset RFFNet dari split resmi."""
    train_set = RFFNetDataset("train", root, train=True, with_mask=with_mask, image_size=image_size)
    val_set = RFFNetDataset("val", root, train=False, with_mask=with_mask, image_size=image_size)
    test_set = RFFNetDataset("test", root, train=False, with_mask=with_mask, image_size=image_size)
    print(f"[dataset_rffnet] train={len(train_set)}  val={len(val_set)}  test={len(test_set)}")
    return train_set, val_set, test_set


if __name__ == "__main__":
    # Sanity check mask_to_bboxes tanpa data asli
    fake_mask = np.zeros((100, 100), dtype=np.uint8)
    fake_mask[10:30, 10:30] = 125  # blok asap
    fake_mask[60:80, 60:90] = 255  # blok api
    boxes = mask_to_bboxes(fake_mask)
    assert len(boxes) == 2, boxes
    cls_ids = sorted(b[0] for b in boxes)
    assert cls_ids == [1, 2], cls_ids
    print("Tes mask_to_bboxes: OK ->", boxes)

    print("\nSemua sanity check src/data/dataset_rffnet.py LOLOS (tanpa data asli).")
