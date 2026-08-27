"""src/models/modality_dropout.py

Modality dropout (Bagian 3.4 concept paper) -- kontribusi inti proyek. Cuma aktif
saat training (`model.train()`); salah satu embedding (RGB atau termal) dijatuhkan
(dinolkan) secara acak per-sample dengan probabilitas `p`, supaya model belajar
tetap berfungsi saat satu sensor hilang total di inference (bukan cuma oklusi
parsial -- inilah diferensiasi eksplisit terhadap RFFNet, lihat Bagian 9 catatan 1).
"""
from __future__ import annotations

import torch
import torch.nn as nn


class ModalityDropout(nn.Module):
    def __init__(self, p: float = 0.2):
        super().__init__()
        assert 0.0 <= p <= 1.0
        self.p = p

    def forward(self, rgb_tokens: torch.Tensor, thermal_tokens: torch.Tensor):
        if not self.training or self.p <= 0:
            return rgb_tokens, thermal_tokens
        B = rgb_tokens.size(0)
        drop_mask = torch.rand(B, device=rgb_tokens.device) < self.p
        drop_which = torch.randint(0, 2, (B,), device=rgb_tokens.device)  # 0=drop RGB, 1=drop termal
        rgb_out = rgb_tokens.clone()
        thermal_out = thermal_tokens.clone()
        rgb_out[drop_mask & (drop_which == 0)] = 0.0
        thermal_out[drop_mask & (drop_which == 1)] = 0.0
        return rgb_out, thermal_out


if __name__ == "__main__":
    md = ModalityDropout(p=1.0)  # p=1 -- SELALU drop salah satu, buat tes deterministik
    md.train()
    rgb = torch.ones(8, 5, 4)
    thermal = torch.ones(8, 5, 4) * 2
    r_out, t_out = md(rgb, thermal)
    n_rgb_dropped = (r_out.sum(dim=(1, 2)) == 0).sum().item()
    n_thermal_dropped = (t_out.sum(dim=(1, 2)) == 0).sum().item()
    assert n_rgb_dropped + n_thermal_dropped == 8, (n_rgb_dropped, n_thermal_dropped)
    print(f"Tes p=1.0 (train mode): {n_rgb_dropped} RGB dijatuhkan, {n_thermal_dropped} termal dijatuhkan -> OK")

    md.eval()
    r_out2, t_out2 = md(rgb, thermal)
    assert torch.equal(r_out2, rgb) and torch.equal(t_out2, thermal)
    print("Tes eval mode (tidak ada dropout sama sekali): OK")
