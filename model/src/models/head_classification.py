"""src/models/head_classification.py

Head klasifikasi 3-kelas (fire_smoke | fire_no_smoke | no_fire) -- output-nya
LANGSUNG dipakai mengisi field `prediction.label`/`prediction.confidence` di
kontrak API (Bagian 3.4). Label index HARUS sinkron dengan
`src/data/dataset_flame2.py::CLASS_TO_IDX` dan `src/metrics.py::CLASS_LABELS`.
"""
from __future__ import annotations

import torch
import torch.nn as nn

CLASS_LABELS = ["no_fire", "fire_no_smoke", "fire_smoke"]  # HARUS sinkron di 3 file


class ClassificationHead(nn.Module):
    def __init__(self, in_dim: int = 384 * 2, n_classes: int = 3, hidden_dim: int = 256):
        super().__init__()
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.mlp = nn.Sequential(
            nn.Linear(in_dim, hidden_dim), nn.ReLU(inplace=True), nn.Dropout(0.2),
            nn.Linear(hidden_dim, n_classes),
        )

    def forward(self, fused_tokens: torch.Tensor) -> torch.Tensor:
        """fused_tokens: (B, N, in_dim) dari CrossAttentionFusion. Return logit (B, n_classes)
        -- belum softmax, dipanggil pemanggil (train.py pakai CrossEntropyLoss, evaluate.py
        pakai softmax manual untuk isi field `confidence`)."""
        x = fused_tokens.transpose(1, 2)
        x = self.pool(x).squeeze(-1)
        return self.mlp(x)

    @staticmethod
    def logits_to_api_prediction(logits: torch.Tensor) -> list[dict]:
        """Konversi logit batch -> list dict {"label": ..., "confidence": ...} PERSIS
        format field `prediction` di kontrak API Bagian 3.4. Dipanggil dari
        src/evaluate.py / inference service, BUKAN dari dalam training loop."""
        probs = torch.softmax(logits, dim=-1)
        conf, idx = probs.max(dim=-1)
        return [
            {"label": CLASS_LABELS[i.item()], "confidence": round(c.item(), 4)}
            for i, c in zip(idx, conf)
        ]


if __name__ == "__main__":
    head = ClassificationHead()
    fused = torch.randn(4, 256, 768)
    logits = head(fused)
    assert logits.shape == (4, 3), logits.shape
    print("Tes forward: OK ->", logits.shape)

    preds = ClassificationHead.logits_to_api_prediction(logits)
    assert len(preds) == 4
    assert all(p["label"] in CLASS_LABELS for p in preds)
    assert all(0 <= p["confidence"] <= 1 for p in preds)
    print("Tes logits_to_api_prediction: OK ->", preds)
