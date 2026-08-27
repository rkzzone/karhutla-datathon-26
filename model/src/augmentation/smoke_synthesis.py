"""src/augmentation/smoke_synthesis.py

Stage 4 -- injeksi asap sintetis ke citra RGB NYATA (Bagian 5 Stage 4, Bagian 9
catatan 10: "semua sintesis data HARUS dari citra nyata, jangan mengarang termal
dari RGB" -- modul ini cuma menyintesis lapisan ASAP di atas RGB asli, TIDAK
menyentuh kanal termal sama sekali, itu tugas thermal_degradation.py terpisah).

tau (τ) ∈ {0, 0.2, 0.4, 0.6, 0.8, 1.0} -- level opasitas asap, tau=0 = citra bersih,
tau=1 = tertutup asap tebal penuh.
"""
from __future__ import annotations

import numpy as np
import torch


TAU_LEVELS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


def _perlin_like_noise(h: int, w: int, scale: int = 8, seed: int | None = None) -> np.ndarray:
    """Noise halus low-frequency (bukan Perlin asli, tapi cukup untuk mensimulasikan
    tekstur asap yang tidak seragam) -- upsample noise kasar dgn interpolasi bilinear."""
    rng = np.random.default_rng(seed)
    small = rng.random((h // scale + 2, w // scale + 2)).astype(np.float32)
    # upsample manual pakai numpy (hindari dependency tambahan spt cv2 di sini)
    small_t = torch.from_numpy(small).unsqueeze(0).unsqueeze(0)
    up = torch.nn.functional.interpolate(small_t, size=(h, w), mode="bilinear", align_corners=False)
    arr = up.squeeze().numpy()
    return (arr - arr.min()) / (arr.max() - arr.min() + 1e-9)


def inject_synthetic_smoke(
    rgb_image: np.ndarray, tau: float, smoke_color: tuple[int, int, int] = (200, 200, 195), seed: int | None = None
) -> np.ndarray:
    """rgb_image: (H, W, 3) uint8, citra RGB NYATA (bukan sintetis dari awal).
    tau: level opasitas asap, 0.0-1.0.
    Return: (H, W, 3) uint8, citra dengan lapisan asap sintetis dicampur (alpha blend).

    Teknik: alpha blend antara citra asli dan warna asap seragam keabuan, dimodulasi
    noise spasial supaya opasitas tidak rata (mensimulasikan gumpalan asap nyata),
    lalu diberi blur ringan supaya transisi halus.
    """
    assert rgb_image.ndim == 3 and rgb_image.shape[2] == 3, f"Expect (H,W,3), dapat {rgb_image.shape}"
    assert 0.0 <= tau <= 1.0, f"tau harus di [0,1], dapat {tau}"
    h, w, _ = rgb_image.shape

    if tau == 0.0:
        return rgb_image.copy()

    noise = _perlin_like_noise(h, w, scale=max(h, w) // 32, seed=seed)
    alpha_map = tau * (0.5 + 0.5 * noise)  # opasitas bervariasi spasial, dipusatkan di sekitar tau
    alpha_map = np.clip(alpha_map, 0.0, 1.0)[..., None]  # (H, W, 1) utk broadcast ke 3 kanal

    smoke_layer = np.full_like(rgb_image, smoke_color, dtype=np.float32)
    blended = rgb_image.astype(np.float32) * (1 - alpha_map) + smoke_layer * alpha_map
    return np.clip(blended, 0, 255).astype(np.uint8)


def generate_tau_sweep(rgb_image: np.ndarray, tau_levels: tuple = TAU_LEVELS, seed: int | None = None) -> dict:
    """Hasilkan satu citra ber-asap sintetis untuk TIAP level tau -- dipakai
    notebooks_kaggle/03_degradation_curve.ipynb untuk mengevaluasi RGB-saja/
    termal-saja/fusi di tiap level, hasilnya reports/degradation_curve.csv."""
    return {tau: inject_synthetic_smoke(rgb_image, tau, seed=seed) for tau in tau_levels}


if __name__ == "__main__":
    fake_rgb = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)

    clean = inject_synthetic_smoke(fake_rgb, tau=0.0)
    assert np.array_equal(clean, fake_rgb), "tau=0 harus identik dgn citra asli"
    print("Tes tau=0 (harus identik citra asli): OK")

    full_smoke = inject_synthetic_smoke(fake_rgb, tau=1.0, seed=42)
    diff_full = np.abs(full_smoke.astype(int) - fake_rgb.astype(int)).mean()
    partial_smoke = inject_synthetic_smoke(fake_rgb, tau=0.3, seed=42)
    diff_partial = np.abs(partial_smoke.astype(int) - fake_rgb.astype(int)).mean()
    assert diff_full > diff_partial, (diff_full, diff_partial)
    print(f"Tes monotonicity (tau besar -> beda dari asli lebih besar): OK "
          f"(diff@tau=1.0={diff_full:.1f} > diff@tau=0.3={diff_partial:.1f})")

    sweep = generate_tau_sweep(fake_rgb, seed=42)
    assert set(sweep.keys()) == set(TAU_LEVELS)
    assert all(v.shape == fake_rgb.shape for v in sweep.values())
    print(f"Tes generate_tau_sweep: OK -> {len(sweep)} level tau dihasilkan {list(sweep.keys())}")
