"""src/data/dataset_flame3.py

Dataset loader untuk FLAME 3 CV subset (Stage 7 -- regime suhu radiometrik & domain-gap
+ LoRA, stretch goal). Beda dari FLAME2/RFFNet: file ini BELUM pernah diverifikasi
langsung terhadap data asli (FLAME2.zip/RFFNet sudah, lewat inspeksi file nyata --
FLAME3 belum ada di tangan kita). Semua asumsi struktur di bawah ditandai
TODO-VERIFIKASI -- WAJIB dicek ulang begitu `flame3_cv_subset.csv` dan raw data dari
Tim data (Stage 0) tersedia, SEBELUM dipakai untuk training/evaluasi Stage 7.

Asumsi kerja: FLAME3 CV subset berisi "kuartet"
TIFF radiometrik -- diasumsikan 4 file per sampel (RGB + termal radiometrik + 2 file
pendukung, kemungkinan pasangan siang/malam atau band tambahan; JUMLAH & MAKNA PASTI
belum dikonfirmasi). TIFF termal di sini diasumsikan menyimpan nilai piksel float
dalam satuan derajat Celsius (radiometrik = terkalibrasi, bukan intensitas 0-255
seperti FLAME2) -- ini beda penting dari FLAME2 dan MEMPENGARUHI cara normalisasi.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms as T

RGB_MEAN, RGB_STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]


def read_radiometric_tiff(path: Path) -> np.ndarray:
    """Baca TIFF radiometrik -> array float (diasumsikan satuan Celsius).
    TODO-VERIFIKASI: konfirmasi satuan asli (Celsius vs Kelvin vs raw sensor count)
    begitu sampel TIFF asli FLAME3 tersedia -- baca metadata/README FLAME3 resminya.
    PIL cukup untuk baca TIFF single-channel float; kalau ternyata multi-band atau
    perlu library khusus (mis. `tifffile` untuk metadata radiometrik penuh), ganti
    baris di bawah."""
    img = Image.open(path)
    arr = np.array(img, dtype=np.float32)
    return arr


def temperature_to_normalized_tensor(temp_arr: np.ndarray, t_min: float = 0.0, t_max: float = 150.0) -> torch.Tensor:
    """Normalisasi suhu radiometrik (Celsius, asumsi rentang wajar kebakaran lahan
    gambut) ke [0, 1] sebelum masuk encoder termal yang sama dgn Stage 1/2.
    TODO-VERIFIKASI: rentang t_min/t_max ini tebakan awal -- sesuaikan setelah
    lihat distribusi suhu asli FLAME3 (Stage 7a butuh persentil suhu per sampel,
    jadi cek dulu skala datanya di sana)."""
    clipped = np.clip(temp_arr, t_min, t_max)
    normalized = (clipped - t_min) / (t_max - t_min)
    return torch.from_numpy(normalized).unsqueeze(0).float()  # (1, H, W)


def temperature_percentile(temp_arr: np.ndarray, percentile: float = 95.0) -> float:
    """Dipakai Stage 7a (partisi kuartet berdasar persentil suhu piksel per bin)."""
    return float(np.percentile(temp_arr, percentile))


def load_flame3_manifest(manifest_path: Path) -> List[dict]:
    """Baca flame3_cv_subset.csv (dari tim data, Stage 0). TODO-VERIFIKASI kolom
    persis begitu file asli tersedia -- diasumsikan minimal ada `quartet_id`,
    `rgb_path`, `thermal_tiff_path`, dan opsional 2 path pendukung lain."""
    with open(manifest_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert rows, f"Manifest kosong: {manifest_path}"
    required = {"quartet_id", "rgb_path", "thermal_tiff_path"}
    missing = required - set(rows[0].keys())
    assert not missing, (
        f"Kolom wajib tidak ada di manifest: {missing}. TODO-VERIFIKASI nama kolom asli "
        f"di flame3_cv_subset.csv dan sesuaikan load_flame3_manifest()."
    )
    return rows


class FLAME3Dataset(Dataset):
    """RGB + termal radiometrik FLAME3 -- dipakai utk (a) evaluasi zero-shot
    FLAME2->FLAME3, (b) subset adaptasi LoRA (N in {10,25,50,100}), (c) partisi
    bin suhu (Stage 7a).

    PENTING (Bagian 3.8 #3): sampel yang dipakai ADAPTASI LoRA tidak boleh sama
    dengan sampel yang dipakai MENGUKUR hasil adaptasi -- split ini WAJIB dilakukan
    di level manifest (lihat `split_for_lora()` di bawah), bukan di dalam kelas ini.
    """

    def __init__(self, rows: List[dict], root: Path, image_size: int = 224,
                 t_min: float = 0.0, t_max: float = 150.0):
        self.rows = rows
        self.root = root
        self.image_size = image_size
        self.t_min, self.t_max = t_min, t_max
        self.rgb_norm = T.Compose([T.Resize((image_size, image_size)), T.ToTensor(), T.Normalize(RGB_MEAN, RGB_STD)])

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int):
        row = self.rows[idx]
        rgb = Image.open(self.root / row["rgb_path"]).convert("RGB")
        rgb_t = self.rgb_norm(rgb)

        temp_arr = read_radiometric_tiff(self.root / row["thermal_tiff_path"])
        thermal_t = temperature_to_normalized_tensor(temp_arr, self.t_min, self.t_max)
        thermal_t = torch.nn.functional.interpolate(
            thermal_t.unsqueeze(0), size=(self.image_size, self.image_size), mode="bilinear", align_corners=False
        ).squeeze(0)

        p95_temp = temperature_percentile(temp_arr, 95.0)
        return rgb_t, thermal_t, {"quartet_id": row["quartet_id"], "p95_temp_celsius": p95_temp}


def split_for_lora(
    rows: List[dict], n_adapt: int, seed: int = 42
) -> Tuple[List[dict], List[dict]]:
    """Pisahkan manifest jadi (subset_adaptasi, subset_evaluasi) -- TIDAK BOLEH tumpang
    tindih (Bagian 3.8 #3). n_adapt in {10, 25, 50, 100} sesuai Stage 7b."""
    import random
    rng = random.Random(seed)
    shuffled = rows[:]
    rng.shuffle(shuffled)
    assert n_adapt < len(shuffled), "n_adapt harus lebih kecil dari total sampel manifest"
    adapt_rows = shuffled[:n_adapt]
    eval_rows = shuffled[n_adapt:]
    return adapt_rows, eval_rows


def bin_by_temperature_percentile(
    manifest_with_temp: List[Tuple[dict, float]], n_bins: int = 3
) -> Dict[int, List[dict]]:
    """Stage 7a: partisi kuartet Fire berdasar persentil suhu piksel -> {bin_idx: [rows]}.
    manifest_with_temp: list of (row, p95_temp_celsius), biasanya dihasilkan dgn
    menjalankan FLAME3Dataset sekali dan mengumpulkan metadata suhu tiap sampel."""
    temps = [t for _, t in manifest_with_temp]
    edges = np.percentile(temps, np.linspace(0, 100, n_bins + 1))
    bins: Dict[int, List[dict]] = {i: [] for i in range(n_bins)}
    for row, t in manifest_with_temp:
        bin_idx = min(int(np.searchsorted(edges, t, side="right")) - 1, n_bins - 1)
        bin_idx = max(bin_idx, 0)
        bins[bin_idx].append(row)
    return bins


if __name__ == "__main__":
    # Sanity check logic murni (tanpa file TIFF asli)
    fake_temp = np.array([[20.0, 30.0], [200.0, 300.0]], dtype=np.float32)  # ada outlier di luar rentang
    normalized = temperature_to_normalized_tensor(fake_temp, t_min=0.0, t_max=150.0)
    assert normalized.shape == (1, 2, 2)
    assert normalized.max().item() <= 1.0 and normalized.min().item() >= 0.0
    print("Tes temperature_to_normalized_tensor (clip outlier): OK ->", normalized.squeeze().tolist())

    p95 = temperature_percentile(fake_temp, 95.0)
    print("Tes temperature_percentile: OK ->", p95)

    fake_rows = [{"quartet_id": str(i)} for i in range(100)]
    adapt, eva = split_for_lora(fake_rows, n_adapt=25)
    assert len(adapt) == 25 and len(eva) == 75
    assert set(r["quartet_id"] for r in adapt).isdisjoint(set(r["quartet_id"] for r in eva))
    print("Tes split_for_lora (tidak overlap): OK")

    fake_with_temp = [({"id": i}, float(i)) for i in range(30)]
    bins = bin_by_temperature_percentile(fake_with_temp, n_bins=3)
    assert sum(len(v) for v in bins.values()) == 30
    print("Tes bin_by_temperature_percentile: OK ->", {k: len(v) for k, v in bins.items()})

    print("\nSemua sanity check src/data/dataset_flame3.py LOLOS (tanpa data asli -- "
          "STRUKTUR FILE BELUM DIVERIFIKASI, cek ulang begitu data FLAME3 tersedia).")
