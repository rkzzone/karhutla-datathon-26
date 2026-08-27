"""src/augmentation/thermal_degradation.py

Stage 4 -- simulasi degradasi kanal TERMAL (drift NUC, noise, blur), dijalankan
di kanal termal NYATA (bukan mengarang termal dari RGB -- lihat Bagian 9 catatan
10). tau (τ) yang sama dipakai smoke_synthesis.py juga mengontrol intensitas
degradasi termal di sini, supaya kurva degradasi RGB dan termal sinkron levelnya
saat dibandingkan di Stage 4.

Tiga jenis degradasi disimulasikan:
  1. Drift NUC (Non-Uniformity Correction) -- pola noise tetap/tersusun (fixed-pattern
     noise) yang muncul saat kalibrasi sensor termal drift seiring waktu/suhu.
  2. Noise sensor -- random Gaussian, mensimulasikan derau elektronik.
  3. Blur -- mensimulasikan fokus tidak sempurna / gerakan drone.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

TAU_LEVELS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


def _gaussian_blur(thermal: np.ndarray, sigma: float) -> np.ndarray:
    """Blur pakai konvolusi Gaussian manual lewat torch (hindari dependency cv2 di
    modul ini, walau cv2 sudah dipakai di tempat lain -- biar modul ini ringan)."""
    if sigma <= 0:
        return thermal
    radius = max(1, int(3 * sigma))
    x = torch.arange(-radius, radius + 1, dtype=torch.float32)
    kernel_1d = torch.exp(-x ** 2 / (2 * sigma ** 2))
    kernel_1d = kernel_1d / kernel_1d.sum()

    t = torch.from_numpy(thermal).float().unsqueeze(0).unsqueeze(0)  # (1,1,H,W)
    kx = kernel_1d.view(1, 1, 1, -1)
    ky = kernel_1d.view(1, 1, -1, 1)
    t = F.conv2d(t, kx, padding=(0, radius))
    t = F.conv2d(t, ky, padding=(radius, 0))
    return t.squeeze().numpy()


def _nuc_drift_pattern(h: int, w: int, strength: float, seed: int | None = None) -> np.ndarray:
    """Pola fixed-pattern noise -- garis-garis horizontal/vertikal halus khas
    sensor microbolometer yang butuh kalibrasi ulang (NUC)."""
    rng = np.random.default_rng(seed)
    row_bias = rng.normal(0, strength, size=(h, 1))
    col_bias = rng.normal(0, strength * 0.5, size=(1, w))
    return row_bias + col_bias  # broadcast -> (H, W)


def degrade_thermal(
    thermal_image: np.ndarray, tau: float, seed: int | None = None
) -> np.ndarray:
    """thermal_image: (H, W) uint8 atau float, citra termal NYATA (satu kanal).
    tau: level degradasi 0.0-1.0 (sinkron dgn smoke_synthesis.TAU_LEVELS).
    Return: (H, W) array sama tipe/rentang dgn input, sudah didegradasi.
    """
    assert thermal_image.ndim == 2, f"Expect (H,W) satu kanal, dapat {thermal_image.shape}"
    assert 0.0 <= tau <= 1.0

    orig_dtype = thermal_image.dtype
    arr = thermal_image.astype(np.float32)
    if tau == 0.0:
        return thermal_image.copy()

    h, w = arr.shape
    max_val = 255.0 if orig_dtype == np.uint8 else float(arr.max() if arr.max() > 0 else 1.0)

    nuc = _nuc_drift_pattern(h, w, strength=tau * max_val * 0.08, seed=seed)
    arr = arr + nuc

    rng = np.random.default_rng(seed)
    gaussian_noise = rng.normal(0, tau * max_val * 0.05, size=(h, w))
    arr = arr + gaussian_noise

    arr = _gaussian_blur(arr, sigma=tau * 2.0)

    arr = np.clip(arr, 0, max_val)
    return arr.astype(orig_dtype)


def generate_tau_sweep(thermal_image: np.ndarray, tau_levels: tuple = TAU_LEVELS, seed: int | None = None) -> dict:
    """Analog smoke_synthesis.generate_tau_sweep tapi untuk kanal termal. Dipanggil
    berpasangan dgn smoke_synthesis di level tau yang SAMA saat membangun kurva
    degradasi (notebooks_kaggle/03_degradation_curve.ipynb)."""
    return {tau: degrade_thermal(thermal_image, tau, seed=seed) for tau in tau_levels}


if __name__ == "__main__":
    fake_thermal = np.random.randint(50, 200, (64, 64), dtype=np.uint8)

    clean = degrade_thermal(fake_thermal, tau=0.0)
    assert np.array_equal(clean, fake_thermal)
    print("Tes tau=0 (harus identik citra asli): OK")

    degraded_full = degrade_thermal(fake_thermal, tau=1.0, seed=42)
    diff_full = np.abs(degraded_full.astype(int) - fake_thermal.astype(int)).mean()
    degraded_partial = degrade_thermal(fake_thermal, tau=0.3, seed=42)
    diff_partial = np.abs(degraded_partial.astype(int) - fake_thermal.astype(int)).mean()
    assert diff_full > diff_partial, (diff_full, diff_partial)
    print(f"Tes monotonicity: OK (diff@tau=1.0={diff_full:.1f} > diff@tau=0.3={diff_partial:.1f})")
    assert degraded_full.dtype == fake_thermal.dtype
    print("Tes dtype dipertahankan (uint8):", degraded_full.dtype)

    sweep = generate_tau_sweep(fake_thermal, seed=42)
    assert set(sweep.keys()) == set(TAU_LEVELS)
    print(f"Tes generate_tau_sweep: OK -> {len(sweep)} level")
