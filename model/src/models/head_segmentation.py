"""src/models/head_segmentation.py

Head segmentasi ringan (Stage 6 Jalur B) -- 3 blok
upsampling, dilatih DI ATAS ENCODER BEKU (frozen encoder, cuma head ini yang
di-training) pakai 555 mask train RFFNet. Dibandingkan terhadap Jalur A (attention
rollout, tanpa label tambahan) di `rffnet_test.csv` -- lihat
notebooks_kaggle/05_localization_ablation.ipynb.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class SegmentationHead(nn.Module):
    def __init__(self, in_dim: int = 384 * 2, n_classes: int = 3, grid: int = 16, image_size: int = 224):
        super().__init__()
        self.grid = grid
        self.image_size = image_size
        self.reduce = nn.Conv2d(in_dim, 256, kernel_size=1)
        self.up = nn.Sequential(
            nn.ConvTranspose2d(256, 128, kernel_size=4, stride=2, padding=1),
            nn.BatchNorm2d(128), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(128, 64, kernel_size=4, stride=2, padding=1),
            nn.BatchNorm2d(64), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(64, n_classes, kernel_size=4, stride=2, padding=1),
        )

    def forward(self, fused_tokens: torch.Tensor) -> torch.Tensor:
        """fused_tokens: (B, N, in_dim). Return logit per piksel (B, n_classes, image_size, image_size)."""
        B, N, C = fused_tokens.shape
        x = fused_tokens.transpose(1, 2).reshape(B, C, self.grid, self.grid)
        x = self.reduce(x)
        x = self.up(x)
        return F.interpolate(x, size=(self.image_size, self.image_size), mode="bilinear", align_corners=False)

    @staticmethod
    def logits_to_heatmap_png_bytes(logits: torch.Tensor, class_idx: int = 2) -> bytes:
        """Konversi logit (1, n_classes, H, W) SATU sampel -> PNG grayscale heatmap
        utk kelas tertentu (default: kelas 'api'/fire, index 2), dipakai mengisi
        field `localization.heatmap_path` di kontrak API. Dipanggil dari inference
        service, bukan training loop.
        """
        import io
        from PIL import Image
        import numpy as np

        probs = torch.softmax(logits, dim=1)[0, class_idx]  # (H, W), 0-1
        arr = (probs.detach().cpu().numpy() * 255).astype(np.uint8)
        img = Image.fromarray(arr, mode="L")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


if __name__ == "__main__":
    head = SegmentationHead()
    fused = torch.randn(2, 256, 768)
    out = head(fused)
    assert out.shape == (2, 3, 224, 224), out.shape
    print("Tes forward: OK ->", out.shape)

    png_bytes = SegmentationHead.logits_to_heatmap_png_bytes(out[:1])
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # magic number PNG
    print(f"Tes logits_to_heatmap_png_bytes: OK -> {len(png_bytes)} bytes, valid PNG header")
