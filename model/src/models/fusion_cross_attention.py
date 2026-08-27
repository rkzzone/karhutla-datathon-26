"""src/models/fusion_cross_attention.py

Fusi cross-attention dua arah -- kontribusi teknis inti proyek (Bagian 1.2, Lampiran
A concept paper). 2 layer, 6 head, dim 384 -> gabung jadi representasi 768-dim per
token. RGB attend ke termal DAN termal attend ke RGB, tiap layer.

PENTING -- grid mismatch: RGBEncoder (DINOv2 patch14, input 224) menghasilkan grid
16x16=256 token. ThermalEncoder (4x downsample stride2 = stride16) menghasilkan
grid 14x14=196 token. Dua grid ini HARUS disamakan dulu (lewat interpolasi bilinear)
sebelum cross-attention, supaya index token merujuk lokasi fisik yang sama --
kalau tidak, `torch.cat` di akhir forward() akan gagal (dimensi token count beda).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def align_token_grid(tokens: torch.Tensor, target_grid: int) -> torch.Tensor:
    """Interpolasi grid token spasial (mis. 14x14 dari ThermalEncoder) ke ukuran
    target_grid (mis. 16x16 dari RGBEncoder)."""
    B, N, C = tokens.shape
    src_grid = int(round(N ** 0.5))
    if src_grid == target_grid:
        return tokens
    x = tokens.transpose(1, 2).reshape(B, C, src_grid, src_grid)
    x = F.interpolate(x, size=(target_grid, target_grid), mode="bilinear", align_corners=False)
    return x.flatten(2).transpose(1, 2)


class CrossAttentionBlock(nn.Module):
    """Satu arah cross-attention: query dari modalitas A, key/value dari modalitas B."""

    def __init__(self, dim: int = 384, n_heads: int = 6):
        super().__init__()
        self.attn = nn.MultiheadAttention(dim, n_heads, batch_first=True)
        self.norm_q = nn.LayerNorm(dim)
        self.norm_kv = nn.LayerNorm(dim)
        self.mlp = nn.Sequential(nn.Linear(dim, dim * 4), nn.GELU(), nn.Linear(dim * 4, dim))
        self.norm_mlp = nn.LayerNorm(dim)

    def forward(self, query_tokens: torch.Tensor, kv_tokens: torch.Tensor,
                attn_bias: torch.Tensor | None = None) -> torch.Tensor:
        """attn_bias: opsional, dipakai src/models/reliability_gate.py (Stage 5) untuk
        memodulasi bobot attention berdasar skor keandalan modalitas."""
        q, kv = self.norm_q(query_tokens), self.norm_kv(kv_tokens)
        attn_out, _ = self.attn(q, kv, kv)
        if attn_bias is not None:
            attn_out = attn_out * attn_bias
        x = query_tokens + attn_out
        return x + self.mlp(self.norm_mlp(x))


class CrossAttentionFusion(nn.Module):
    N_LAYERS = 2

    def __init__(self, dim: int = 384, n_heads: int = 6, rgb_grid: int = 16):
        super().__init__()
        self.rgb_grid = rgb_grid
        self.rgb_to_thermal = nn.ModuleList([CrossAttentionBlock(dim, n_heads) for _ in range(self.N_LAYERS)])
        self.thermal_to_rgb = nn.ModuleList([CrossAttentionBlock(dim, n_heads) for _ in range(self.N_LAYERS)])

    def forward(
        self,
        rgb_tokens: torch.Tensor,
        thermal_tokens: torch.Tensor,
        rgb_reliability: torch.Tensor | None = None,
        thermal_reliability: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """rgb_reliability/thermal_reliability: (B,) skor 0-1 dari reliability_gate.py
        (Stage 5) -- kalau diisi, dipakai memodulasi bobot attention. None = perilaku
        Stage 2 (belum ada gating)."""
        thermal_tokens = align_token_grid(thermal_tokens, self.rgb_grid)

        r_bias = thermal_reliability.view(-1, 1, 1) if thermal_reliability is not None else None
        t_bias = rgb_reliability.view(-1, 1, 1) if rgb_reliability is not None else None

        r, t = rgb_tokens, thermal_tokens
        for i in range(self.N_LAYERS):
            r_new = self.rgb_to_thermal[i](r, t, attn_bias=r_bias)   # RGB attend ke termal, dimodulasi keandalan termal
            t_new = self.thermal_to_rgb[i](t, r, attn_bias=t_bias)   # termal attend ke RGB, dimodulasi keandalan RGB
            r, t = r_new, t_new
        return torch.cat([r, t], dim=-1)  # (B, N_token, 2*dim)


if __name__ == "__main__":
    fusion = CrossAttentionFusion()
    rgb_tok = torch.randn(2, 256, 384)      # grid 16x16
    thermal_tok = torch.randn(2, 196, 384)  # grid 14x14 -- BEDA dari rgb, harus dialign otomatis

    out = fusion(rgb_tok, thermal_tok)
    assert out.shape == (2, 256, 768), out.shape
    print("Tes forward tanpa gating: OK ->", out.shape)

    reliability_rgb = torch.rand(2)
    reliability_thermal = torch.rand(2)
    out_gated = fusion(rgb_tok, thermal_tok, reliability_rgb, reliability_thermal)
    assert out_gated.shape == (2, 256, 768), out_gated.shape
    print("Tes forward dengan gating (Stage 5): OK ->", out_gated.shape)

    aligned = align_token_grid(thermal_tok, 16)
    assert aligned.shape == (2, 256, 384), aligned.shape
    print("Tes align_token_grid: OK ->", aligned.shape)
