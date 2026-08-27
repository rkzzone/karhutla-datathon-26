"""src/models/reliability_gate.py

Stage 5 -- Reliability-gated fusion. Gate head ringan yang memprediksi skor
keandalan (0-1) per modalitas, disupervisi REGRESI terhadap `1 - tau` (tau = level
degradasi sintetis dari Stage 4: tau=0 -> data bersih -> target reliability=1;
tau=1 -> degradasi penuh -> target reliability=0).

Skor ini dipakai dua tempat:
  1. Memodulasi bobot cross-attention (lihat fusion_cross_attention.py parameter
     rgb_reliability/thermal_reliability).
  2. Mengisi field `modality_reliability` di kontrak API (Bagian 3.4) -- WAJIB
     angka nyata dari modul ini setelah Stage 5 selesai, bukan placeholder 0.5.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class ReliabilityGate(nn.Module):
    """Input: token spasial (B, N, dim) SATU modalitas (sebelum fusi).
    Output: skor keandalan (B,) di [0, 1] via sigmoid, utk modalitas itu.

    Dipanggil DUA KALI per forward pass (sekali untuk RGB tokens, sekali untuk
    termal tokens) -- lihat contoh pemakaian di src/train.py Stage 5."""

    def __init__(self, dim: int = 384, hidden_dim: int = 128):
        super().__init__()
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.mlp = nn.Sequential(
            nn.Linear(dim, hidden_dim), nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, hidden_dim // 2), nn.ReLU(inplace=True),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        x = tokens.transpose(1, 2)          # (B, dim, N)
        x = self.pool(x).squeeze(-1)        # (B, dim)
        logit = self.mlp(x).squeeze(-1)     # (B,)
        return torch.sigmoid(logit)


class DualReliabilityGate(nn.Module):
    """Wrapper praktis: satu modul yang menghasilkan skor keandalan RGB dan termal
    sekaligus, dipanggil sekali per forward pass model utuh."""

    def __init__(self, dim: int = 384, hidden_dim: int = 128, shared_backbone: bool = False):
        super().__init__()
        if shared_backbone:
            gate = ReliabilityGate(dim, hidden_dim)
            self.rgb_gate = gate
            self.thermal_gate = gate  # bobot dibagi -- lebih hemat parameter, opsional
        else:
            self.rgb_gate = ReliabilityGate(dim, hidden_dim)
            self.thermal_gate = ReliabilityGate(dim, hidden_dim)

    def forward(self, rgb_tokens: torch.Tensor, thermal_tokens: torch.Tensor):
        return self.rgb_gate(rgb_tokens), self.thermal_gate(thermal_tokens)


def reliability_regression_loss(
    pred_rgb: torch.Tensor, pred_thermal: torch.Tensor,
    tau_rgb: torch.Tensor, tau_thermal: torch.Tensor,
) -> torch.Tensor:
    """MSE terhadap target (1 - tau) per modalitas -- tau=0 (bersih) -> target=1,
    tau=1 (degradasi penuh) -> target=0. tau_rgb/tau_thermal: (B,) dari Stage 4."""
    target_rgb = 1.0 - tau_rgb
    target_thermal = 1.0 - tau_thermal
    return torch.nn.functional.mse_loss(pred_rgb, target_rgb) + \
        torch.nn.functional.mse_loss(pred_thermal, target_thermal)


if __name__ == "__main__":
    gate = DualReliabilityGate()
    rgb_tok = torch.randn(4, 256, 384)
    thermal_tok = torch.randn(4, 196, 384)
    r_score, t_score = gate(rgb_tok, thermal_tok)
    assert r_score.shape == (4,) and t_score.shape == (4,)
    assert (r_score >= 0).all() and (r_score <= 1).all()
    print("Tes forward DualReliabilityGate: OK -> rgb:", r_score.tolist(), " thermal:", t_score.tolist())

    tau_rgb = torch.tensor([0.0, 0.5, 1.0, 0.2])
    tau_thermal = torch.tensor([1.0, 0.5, 0.0, 0.8])
    loss = reliability_regression_loss(r_score, t_score, tau_rgb, tau_thermal)
    assert loss.item() >= 0
    print("Tes reliability_regression_loss: OK ->", loss.item())
