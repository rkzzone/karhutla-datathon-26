"""src/models/encoder_thermal.py

CNN ringan 4 blok (32->64->128->256), dilatih dari nol -- tidak ada backbone
termal besar yang publicly available utk transfer learning (Lampiran A concept
paper). Arsitektur ini SENGAJA identik dgn versi yg sudah dipakai di
notebooks_kaggle/01_pretrain_thermal.ipynb rekan tim sebelumnya, supaya checkpoint
lama tetap kompatibel kalau mau dipakai sbg starting point.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class ThermalEncoder(nn.Module):
    EMBED_DIM = 384
    CHANNELS = (32, 64, 128, 256)

    def __init__(self, in_channels: int = 1, embedding_dim: int = EMBED_DIM):
        super().__init__()
        blocks = []
        prev = in_channels
        for out_ch in self.CHANNELS:
            blocks.append(nn.Sequential(
                nn.Conv2d(prev, out_ch, 3, 1, 1, bias=False), nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
                nn.Conv2d(out_ch, out_ch, 3, 1, 1, bias=False), nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
                nn.MaxPool2d(2, 2),
            ))
            prev = out_ch
        self.blocks = nn.Sequential(*blocks)
        self.proj = nn.Conv2d(self.CHANNELS[-1], embedding_dim, kernel_size=1)

    def trainable_parameter_summary(self) -> str:
        n_params = sum(p.numel() for p in self.parameters())
        return f"ThermalEncoder: {n_params/1e6:.2f}M params (semua trainable, dilatih dari nol)"

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, 1, H, W) sudah dinormalisasi. Return token spasial (B, N_patch, embed_dim),
        stride total 16 (4x maxpool stride 2) -- beda dari RGBEncoder (stride 14, DINOv2
        patch14), lihat src/models/fusion_cross_attention.py::align_token_grid untuk
        penyelarasan grid sebelum cross-attention."""
        feat_map = self.proj(self.blocks(x))         # (B, embed_dim, H/16, W/16)
        B, C, H, W = feat_map.shape
        return feat_map.flatten(2).transpose(1, 2)    # (B, H*W, embed_dim)


if __name__ == "__main__":
    model = ThermalEncoder()
    print(model.trainable_parameter_summary())
    dummy = torch.randn(2, 1, 224, 224)
    out = model(dummy)
    assert out.shape == (2, 14 * 14, 384), out.shape  # 224/16=14
    print("Tes forward shape: OK ->", out.shape)
