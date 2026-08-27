"""src/models/lora_adapter.py

Stage 7b -- adaptasi domain-gap (FLAME2 -> FLAME3) lewat LoRA (Low-Rank Adaptation),
dipakai dengan N in {10, 25, 50, 100} sampel FLAME3 (Bagian 5 Stage 7, Bagian 3.8 #3).

Prinsip: bekukan SELURUH bobot model fusi (`fusion_v2_gated.pth`), tempel matriks
low-rank kecil (A, B) di layer Linear yang dipilih, cuma A dan B yang di-training.
Ini jauh lebih murah dari fine-tune penuh dan cocok untuk adaptasi data sangat kecil
(N<=100) tanpa overfitting parah.
"""
from __future__ import annotations

import math

import torch
import torch.nn as nn


class LoRALinear(nn.Module):
    """Bungkus satu nn.Linear yang sudah ada dengan adapter low-rank:
    y = W_frozen(x) + (alpha/rank) * B(A(x))
    W_frozen dibekukan; cuma A, B yang trainable.
    """

    def __init__(self, base_linear: nn.Linear, rank: int = 8, alpha: float = 16.0):
        super().__init__()
        self.base = base_linear
        for p in self.base.parameters():
            p.requires_grad = False

        in_features, out_features = base_linear.in_features, base_linear.out_features
        self.rank = rank
        self.scale = alpha / rank

        self.lora_A = nn.Parameter(torch.zeros(rank, in_features))
        self.lora_B = nn.Parameter(torch.zeros(out_features, rank))
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        # lora_B sengaja diinisiasi nol -- di awal training, adapter tidak mengubah
        # output sama sekali (delta = 0), training dimulai dari perilaku model asli.

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base_out = self.base(x)
        delta = (x @ self.lora_A.T) @ self.lora_B.T
        return base_out + self.scale * delta

    def trainable_parameter_count(self) -> int:
        return self.lora_A.numel() + self.lora_B.numel()


def inject_lora_into_linear_layers(
    module: nn.Module, target_names: tuple[str, ...] = ("qkv", "proj", "fc1", "fc2"),
    rank: int = 8, alpha: float = 16.0,
) -> int:
    """Cari semua nn.Linear di dalam `module` yang nama atribut-nya cocok
    `target_names`, ganti jadi LoRALinear IN-PLACE. Return jumlah layer yang diganti.

    Dipanggil di src/train.py Stage 7 sebelum training LoRA -- contoh:
        n = inject_lora_into_linear_layers(fusion_model.fusion, rank=8)
        print(f"{n} layer Linear diganti jadi LoRALinear")
    """
    count = 0
    for name, child in list(module.named_children()):
        if isinstance(child, nn.Linear) and any(t in name for t in target_names):
            setattr(module, name, LoRALinear(child, rank=rank, alpha=alpha))
            count += 1
        else:
            count += inject_lora_into_linear_layers(child, target_names, rank, alpha)
    return count


def count_trainable_parameters(model: nn.Module) -> tuple[int, int]:
    """Return (n_trainable, n_total) -- dipakai memverifikasi bahwa LoRA beneran
    cuma melatih sebagian kecil parameter (biasanya <1% dari total)."""
    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    n_total = sum(p.numel() for p in model.parameters())
    return n_trainable, n_total


if __name__ == "__main__":
    base = nn.Linear(384, 384)
    lora = LoRALinear(base, rank=8, alpha=16.0)

    x = torch.randn(2, 10, 384)
    out_before_train = lora(x)
    base_out = base(x)
    # lora_B diinisiasi nol -> delta=0 -> output HARUS identik dgn base linear murni di awal
    assert torch.allclose(out_before_train, base_out, atol=1e-5), "LoRA di awal harus = base (B diinit nol)"
    print("Tes inisialisasi LoRA (delta=0 di awal): OK")

    n_trainable, n_total = count_trainable_parameters(lora)
    print(f"Tes hitung parameter: {n_trainable} trainable dari {n_total} total "
          f"({n_trainable/n_total*100:.2f}%) -- HARUS jauh lebih kecil dari 100%")
    assert n_trainable < n_total

    class DummyBlock(nn.Module):
        def __init__(self):
            super().__init__()
            self.qkv = nn.Linear(384, 384 * 3)
            self.proj = nn.Linear(384, 384)
            self.unrelated = nn.Linear(384, 10)  # nama tidak match target_names -- harus TIDAK diganti

    block = DummyBlock()
    n_replaced = inject_lora_into_linear_layers(block, rank=4)
    assert n_replaced == 2, n_replaced
    assert isinstance(block.qkv, LoRALinear) and isinstance(block.proj, LoRALinear)
    assert isinstance(block.unrelated, nn.Linear) and not isinstance(block.unrelated, LoRALinear)
    print(f"Tes inject_lora_into_linear_layers: OK -> {n_replaced} layer diganti (qkv, proj), "
          f"'unrelated' TIDAK diganti sesuai target_names")
