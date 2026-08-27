"""src/models/encoder_rgb.py

DINOv2 ViT-S/14, 9 dari 12 blok dibekukan, 3 blok terakhir + LayerNorm di-fine-tune
(Stage 1; Lampiran A concept paper).
"""
from __future__ import annotations

import torch
import torch.nn as nn


class RGBEncoder(nn.Module):
    N_FROZEN_BLOCKS = 9
    EMBED_DIM = 384

    def __init__(self, embedding_dim: int = EMBED_DIM, n_frozen_blocks: int = N_FROZEN_BLOCKS):
        super().__init__()
        self.backbone = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14")
        assert self.backbone.embed_dim == embedding_dim, (
            f"Embed dim DINOv2 ({self.backbone.embed_dim}) != embedding_dim yg diminta ({embedding_dim})"
        )

        for param in self.backbone.parameters():
            param.requires_grad = False
        total_blocks = len(self.backbone.blocks)
        assert n_frozen_blocks < total_blocks, "n_frozen_blocks harus < total blok backbone"
        for blk in self.backbone.blocks[n_frozen_blocks:]:
            for p in blk.parameters():
                p.requires_grad = True
        for p in self.backbone.norm.parameters():
            p.requires_grad = True

        self.n_frozen_blocks = n_frozen_blocks
        self.total_blocks = total_blocks

    def trainable_parameter_summary(self) -> str:
        n_trainable = sum(p.numel() for p in self.backbone.parameters() if p.requires_grad)
        n_total = sum(p.numel() for p in self.backbone.parameters())
        return (f"RGBEncoder: {n_total/1e6:.1f}M total, {n_trainable/1e6:.1f}M trainable "
                f"(blok {self.n_frozen_blocks}-{self.total_blocks-1} + LayerNorm)")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, 3, H, W) sudah dinormalisasi ImageNet mean/std.
        Return patch tokens (B, N_patch, embed_dim) -- CLS token dibuang, dipakai
        modul-modul hilir yg butuh info spasial (fusi, segmentasi, deteksi)."""
        out = self.backbone.forward_features(x)
        return out["x_norm_patchtokens"]

    def forward_with_cls(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Varian yg juga mengembalikan CLS token -- dipakai kalau ada modul hilir
        yg butuh representasi global (bukan spasial), mis. head klasifikasi sederhana."""
        out = self.backbone.forward_features(x)
        return out["x_norm_patchtokens"], out["x_norm_clstoken"]


if __name__ == "__main__":
    print("Modul ini butuh unduh bobot DINOv2 dari torch.hub (perlu internet) -- "
          "tidak dijalankan otomatis di sanity check offline. Struktur kelas sudah "
          "divalidasi lewat import Python murni (tidak ada syntax error).")
