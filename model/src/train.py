"""src/train.py

Entry point training tunggal untuk seluruh stage tim model (1, 2, 4, 5, 6, 7).
Dispatch berdasarkan field `stage` di file config .yaml -- lihat configs/*.yaml.

Pemakaian:
    python src/train.py --config configs/stage1_pretrain_thermal.yaml
    python src/train.py --config configs/stage2_finetune_fusion.yaml
    ... dst

Tiap fungsi train_stageN() menyalin config yang dipakai ke `runs/{run_id}/config.yaml`
begitu run selesai (Bagian 3.3) -- config di `configs/` bisa berubah, runs/ tidak.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # supaya `src.xxx` importable dari root

from src.data.dataset_flame2 import build_flame2_datasets, DEFAULT_VIDEO_FRAME_RANGES
from src.data.dataset_rffnet import build_rffnet_datasets, RFFNetDataset
from src.models.encoder_rgb import RGBEncoder
from src.models.encoder_thermal import ThermalEncoder
from src.models.modality_dropout import ModalityDropout
from src.models.fusion_cross_attention import CrossAttentionFusion
from src.models.head_classification import ClassificationHead
from src.models.head_segmentation import SegmentationHead
from src.models.reliability_gate import DualReliabilityGate, reliability_regression_loss
from src.models.lora_adapter import inject_lora_into_linear_layers, count_trainable_parameters
from torch.amp import autocast, GradScaler  # [PATCH P3]
from src.augmentation.smoke_synthesis import inject_synthetic_smoke, TAU_LEVELS as SMOKE_TAU_LEVELS
from src.augmentation.thermal_degradation import degrade_thermal
from src import metrics as M


def kunci_benih(seed: int):
    """[PATCH P8] Kunci SELURUH sumber keacakan.

    Sebelum patch ini, `seed: 42` tercantum di setiap config tetapi TIDAK PERNAH
    dipakai: tidak ada satu pun torch.manual_seed di seluruh train.py. Akibatnya
    dua run dengan konfigurasi identik dapat berbeda beberapa poin akurasi, dan
    perbandingan antar-konfigurasi tidak dapat dipertanggungjawabkan.
    """
    import random as _rnd
    import numpy as _np
    _rnd.seed(seed)
    _np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    print(f"[P8] seluruh benih dikunci ke {seed}")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_run_artifacts(config: dict, run_dir: Path, extra_metrics: dict | None = None):
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
    if extra_metrics is not None:
        with open(run_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(extra_metrics, f, indent=2)


# =============================================================================
# Stage 1 -- Pretrain encoder termal (klasifikasi 3 kelas, 53k FLAME2)
# =============================================================================

def train_stage1(config: dict, device: torch.device):
    # [PATCH P3] Presisi campuran fp16 dan DataParallel AKTIF di stage ini.
    # Stage 1 adalah yang paling diuntungkan: 6,5-8,5 jam fp32 satu GPU menjadi
    # sekitar 2-3 jam fp16 dua GPU. Naikkan batch_size di config agar dua GPU terisi.
    d = config["data"]
    m = config["model"]
    t = config["training"]
    c = config["checkpoint"]

    train_set, val_set = build_flame2_datasets(
        labels_path=Path(d["labels_path"]),
        manifest_path=Path(d["manifest_path"]),
        dataset_root=Path(d["dataset_root"]),
        excluded_csv_path=Path(d["excluded_csv"]),
        video_frame_ranges=DEFAULT_VIDEO_FRAME_RANGES,
        val_fraction=d["val_fraction"],
        image_size=d["image_size"],
    )
    train_loader = DataLoader(train_set, batch_size=t["batch_size"], shuffle=True, num_workers=4,
                               pin_memory=True, drop_last=True)
    val_loader = DataLoader(val_set, batch_size=t["batch_size"], shuffle=False, num_workers=4, pin_memory=True)

    rgb_encoder = RGBEncoder(m["embedding_dim"], m["rgb_frozen_blocks"]).to(device)
    thermal_encoder = ThermalEncoder(embedding_dim=m["embedding_dim"]).to(device)
    modality_dropout = ModalityDropout(t["modality_dropout_p"]).to(device)
    fusion = CrossAttentionFusion(dim=m["embedding_dim"]).to(device)
    head = ClassificationHead(in_dim=m["embedding_dim"] * 2, n_classes=m["n_classes"]).to(device)

    # [PATCH P3] Stage 1 adalah stage terberat, jadi di sinilah dua GPU paling berguna.
    rgb_encoder = bungkus_dp(rgb_encoder); thermal_encoder = bungkus_dp(thermal_encoder)
    fusion = bungkus_dp(fusion); head = bungkus_dp(head)

    print(buka_dp(rgb_encoder).trainable_parameter_summary())      # [PATCH P3]
    print(buka_dp(thermal_encoder).trainable_parameter_summary())

    params = (
        [p for p in rgb_encoder.parameters() if p.requires_grad]
        + list(thermal_encoder.parameters()) + list(fusion.parameters()) + list(head.parameters())
    )
    optimizer = torch.optim.AdamW(params, lr=t["lr"], weight_decay=t["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t["epochs"])
    criterion = nn.CrossEntropyLoss()

    run_dir = Path(c["out_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)  # WAJIB -- torch.save() tidak auto-buat folder
    best_val_acc = 0.0
    patience = 0
    use_amp = device.type == "cuda"           # [PATCH P3]
    scaler = GradScaler("cuda", enabled=use_amp)

    for epoch in range(1, t["epochs"] + 1):
        t0 = time.time()
        rgb_encoder.train(); thermal_encoder.train(); fusion.train(); head.train()
        train_loss = 0.0
        for rgb, thermal, target in train_loader:
            rgb, thermal, target = rgb.to(device), thermal.to(device), target.to(device)
            optimizer.zero_grad()
            with autocast("cuda", enabled=use_amp, dtype=torch.float16):  # [PATCH P3]
                r_tok, th_tok = rgb_encoder(rgb), thermal_encoder(thermal)
                r_tok, th_tok = modality_dropout(r_tok, th_tok)
                fused = fusion(r_tok, th_tok)
                logits = head(fused)
                loss = criterion(logits, target)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            train_loss += loss.item() * rgb.size(0)
        train_loss /= len(train_set)
        scheduler.step()

        rgb_encoder.eval(); thermal_encoder.eval(); fusion.eval(); head.eval()
        modality_dropout.eval()  # [PATCH P2] nn.Module default training=True
        val_loss, correct, total = 0.0, 0, 0
        with torch.no_grad():
            for rgb, thermal, target in val_loader:
                rgb, thermal, target = rgb.to(device), thermal.to(device), target.to(device)
                with autocast("cuda", enabled=use_amp, dtype=torch.float16):  # [PATCH P3]
                    r_tok, th_tok = rgb_encoder(rgb), thermal_encoder(thermal)
                    fused = fusion(r_tok, th_tok)
                    logits = head(fused)
                val_loss += criterion(logits.float(), target).item() * rgb.size(0)
                correct += (logits.argmax(dim=-1) == target).sum().item()
                total += rgb.size(0)
        val_loss /= len(val_set)
        val_acc = correct / total

        print(f"[Stage1] epoch {epoch}/{t['epochs']}  train_loss={train_loss:.4f}  "
              f"val_loss={val_loss:.4f}  val_acc={val_acc:.4f}  ({time.time()-t0:.1f}s)")

        if epoch % c["save_every_n_epochs"] == 0 or epoch == t["epochs"]:
            torch.save({"thermal_encoder": buka_dp(thermal_encoder).state_dict(),  # [PATCH P3]
                        "epoch": epoch, "val_acc": val_acc},
                       run_dir / "checkpoint_last.pth", _use_new_zipfile_serialization=False)

        # [PATCH P7] Pakai >= supaya saat val_acc mendatar, checkpoint yang tersimpan
        # adalah yang PALING TERLATIH, bukan yang pertama kali mencapai nilai itu.
        # Dengan > saja, plateau membuat encoder epoch 1 yang tersimpan sebagai "best".
        # Patience tetap hanya di-reset saat ada perbaikan sungguhan.
        if val_acc >= best_val_acc:
            patience = 0 if val_acc > best_val_acc else patience + 1
            best_val_acc = val_acc
            torch.save({"thermal_encoder": buka_dp(thermal_encoder).state_dict(),  # [PATCH P3]
                        "epoch": epoch, "val_acc": val_acc},
                       run_dir / "checkpoint_best.pth", _use_new_zipfile_serialization=False)
        else:
            patience += 1
            if patience >= t["early_stop_patience"]:
                print(f"[Stage1] Early stopping di epoch {epoch}")
                break

    best = torch.load(run_dir / "checkpoint_best.pth", map_location=device)
    Path(c["final_path"]).parent.mkdir(parents=True, exist_ok=True)
    torch.save(best, c["final_path"], _use_new_zipfile_serialization=False)
    print(f"[Stage1] Selesai. Best val_acc={best_val_acc:.4f}. Disimpan ke {c['final_path']}")
    save_run_artifacts(config, run_dir, {"best_val_acc": best_val_acc})


# =============================================================================
# Stage 2 -- Fine-tune fusi + Ablation #1 (unimodal vs fusi)
# =============================================================================

def bungkus_dp(m: nn.Module) -> nn.Module:
    """[PATCH P3] Bungkus dengan DataParallel bila ada lebih dari satu GPU."""
    if torch.cuda.device_count() > 1:
        print(f"[P3] DataParallel aktif pada {torch.cuda.device_count()} GPU")
        return nn.DataParallel(m)
    return m


def buka_dp(m: nn.Module) -> nn.Module:
    """[PATCH P3] Buka bungkus SEBELUM menyimpan state_dict.

    DataParallel menambah prefiks 'module.' pada setiap kunci. Bila prefiks itu
    ikut tersimpan, checkpoint tidak akan dapat dimuat oleh kode yang tidak
    memakai DataParallel, termasuk seluruh skrip evaluasi dan inference service.
    """
    return m.module if isinstance(m, nn.DataParallel) else m


def _forward_full_model(rgb, thermal, rgb_encoder, thermal_encoder, modality_dropout, fusion, head,
                         force_drop: str | None = None):
    r_tok, th_tok = rgb_encoder(rgb), thermal_encoder(thermal)
    if force_drop == "rgb":
        r_tok = torch.zeros_like(r_tok)
    elif force_drop == "thermal":
        th_tok = torch.zeros_like(th_tok)
    else:
        r_tok, th_tok = modality_dropout(r_tok, th_tok)
    fused = fusion(r_tok, th_tok)
    return head(fused)


def train_stage2(config: dict, device: torch.device):
    d, m, t, c = config["data"], config["model"], config["training"], config["checkpoint"]

    train_set, val_set, test_set = build_rffnet_datasets(Path(d["rffnet_root"]), with_mask=True,
                                                           image_size=d["image_size"])

    def collate(batch):
        rgb = torch.stack([b[0] for b in batch])
        thermal = torch.stack([b[1] for b in batch])
        seg = torch.stack([b[2] for b in batch])
        has_obj = torch.tensor([b[3] for b in batch])
        # label 3 kelas turunan dari mask: ada api -> fire_smoke/fire_no_smoke; cek ada asap juga
        labels = []
        for i in range(len(batch)):
            s = batch[i][2]
            has_fire = (s == 2).any().item()
            has_smoke = (s == 1).any().item()
            if has_fire and has_smoke:
                labels.append(2)
            elif has_fire:
                labels.append(1)
            else:
                labels.append(0)
        return rgb, thermal, seg, torch.tensor(labels)

    train_loader = DataLoader(train_set, batch_size=t["batch_size"], shuffle=True, num_workers=4,
                               pin_memory=True, drop_last=True, collate_fn=collate)
    val_loader = DataLoader(val_set, batch_size=t["batch_size"], shuffle=False, num_workers=4,
                             pin_memory=True, collate_fn=collate)

    rgb_encoder = RGBEncoder(m["embedding_dim"], m["rgb_frozen_blocks"]).to(device)
    thermal_encoder = ThermalEncoder(embedding_dim=m["embedding_dim"]).to(device)
    if Path(m["pretrained_thermal_encoder"]).exists():
        ckpt = torch.load(m["pretrained_thermal_encoder"], map_location=device)
        thermal_encoder.load_state_dict(ckpt["thermal_encoder"])
        print(f"[Stage2] Bobot thermal_encoder Stage 1 dimuat (val_acc={ckpt.get('val_acc')})")
    else:
        print(f"[Stage2] PERINGATAN: {m['pretrained_thermal_encoder']} tidak ditemukan -- "
              f"thermal_encoder dilatih dari nol tanpa pretraining Stage 1.")

    # [PATCH P4] grid TIDAK pernah disapu di versi lama. Sekarang p dapat di-override
    # lewat --p di CLI, sehingga Ablation #3 (sensitivitas p) benar-benar bisa dijalankan.
    modality_dropout_p = float(t.get("modality_dropout_p", t["modality_dropout_p_grid"][1]))
    print(f"[Stage2] modality_dropout_p = {modality_dropout_p}")
    modality_dropout = ModalityDropout(modality_dropout_p).to(device)
    fusion = CrossAttentionFusion(dim=m["embedding_dim"], n_heads=m["fusion_n_heads"]).to(device)
    head = ClassificationHead(in_dim=m["embedding_dim"] * 2, n_classes=m["n_classes"]).to(device)

    params = ([p for p in rgb_encoder.parameters() if p.requires_grad] + list(thermal_encoder.parameters())
              + list(fusion.parameters()) + list(head.parameters()))
    optimizer = torch.optim.AdamW(params, lr=t["lr"], weight_decay=t["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t["epochs"])
    criterion = nn.CrossEntropyLoss()

    run_dir = Path(c["out_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)  # WAJIB -- torch.save() tidak auto-buat folder
    best_val_acc, patience = 0.0, 0

    for epoch in range(1, t["epochs"] + 1):
        t0 = time.time()
        rgb_encoder.train(); thermal_encoder.train(); fusion.train(); head.train()
        train_loss = 0.0
        for rgb, thermal, seg, labels in train_loader:
            rgb, thermal, labels = rgb.to(device), thermal.to(device), labels.to(device)
            optimizer.zero_grad()
            logits = _forward_full_model(rgb, thermal, rgb_encoder, thermal_encoder, modality_dropout, fusion, head)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * rgb.size(0)
        train_loss /= len(train_set)
        scheduler.step()

        rgb_encoder.eval(); thermal_encoder.eval(); fusion.eval(); head.eval()
        modality_dropout.eval()  # [PATCH P2] nn.Module default training=True
        # [PATCH P9] Kriteria seleksi checkpoint.
        #
        # Sebelum patch ini, checkpoint dipilih berdasarkan akurasi fusi bersih di
        # rffnet_val. Ukuran itu JENUH: pada 12 run RUN 2B rentangnya hanya 98,33
        # sampai 100,00 dengan simpangan 0,65 poin, dan banyak epoch berimpit di
        # 1,0000. Ketika banyak epoch seri, epoch mana yang tersimpan praktis acak
        # terhadap hal yang tidak diukur, yaitu jalur unimodal. Padahal justru
        # jalur unimodal itulah tumpuan seluruh klaim ketahanan. Akibatnya pada
        # RUN 2B akurasi termal-saja berayun 48,33 sampai 97,50, lebar 49 poin,
        # dan sapuan p maupun perbandingan encoder menjadi tak dapat ditafsirkan.
        #
        # Penggantinya: rerata akurasi TIGA mode ketersediaan modalitas. Ini bukan
        # sekadar pilihan yang lebih stabil, melainkan kriteria yang memang sesuai
        # dengan tujuan yang dinyatakan. Melatih dengan modality dropout lalu
        # memilih model dengan akurasi kondisi bersih adalah memilih berdasarkan
        # ukuran yang bukan tujuannya.
        kriteria = t.get("selection_criterion", "rerata_tiga_mode")
        akurasi_mode, val_loss = {}, 0.0
        with torch.no_grad():
            for nama_mode, force_drop in [("fusi", None), ("rgb", "thermal"), ("termal", "rgb")]:
                if kriteria == "fusi" and nama_mode != "fusi":
                    continue
                benar, total = 0, 0
                for rgb, thermal, seg, labels in val_loader:
                    rgb, thermal, labels = rgb.to(device), thermal.to(device), labels.to(device)
                    logits = _forward_full_model(rgb, thermal, rgb_encoder, thermal_encoder,
                                                 modality_dropout, fusion, head, force_drop=force_drop)
                    if nama_mode == "fusi":
                        val_loss += criterion(logits, labels).item() * rgb.size(0)
                    benar += (logits.argmax(-1) == labels).sum().item()
                    total += rgb.size(0)
                akurasi_mode[nama_mode] = benar / total
        val_loss = val_loss / len(val_set)
        val_acc = akurasi_mode["fusi"]
        val_acc_rerata = sum(akurasi_mode.values()) / len(akurasi_mode)
        skor_seleksi = val_acc if kriteria == "fusi" else val_acc_rerata

        print(f"[Stage2] epoch {epoch}/{t['epochs']}  train_loss={train_loss:.4f}  "
              f"val_loss={val_loss:.4f}  val_acc={val_acc:.4f}  "
              f"rgb={akurasi_mode.get('rgb', float('nan')):.4f}  "
              f"termal={akurasi_mode.get('termal', float('nan')):.4f}  "
              f"SKOR={skor_seleksi:.4f}  ({time.time()-t0:.1f}s)")

        state = {"rgb_encoder": rgb_encoder.state_dict(), "thermal_encoder": thermal_encoder.state_dict(),
                 "fusion": fusion.state_dict(), "head_classification": head.state_dict(), "epoch": epoch,
                 "val_acc": val_acc, "modality_dropout_p": modality_dropout_p,
                 "val_acc_per_mode": akurasi_mode, "val_acc_rerata": val_acc_rerata,
                 "selection_criterion": kriteria}

        if epoch % c["save_every_n_epochs"] == 0 or epoch == t["epochs"]:
            torch.save(state, run_dir / "checkpoint_last.pth", _use_new_zipfile_serialization=False)
        # [PATCH P7] lihat penjelasan di Stage 1. [PATCH P9] skor, bukan val_acc.
        if skor_seleksi >= best_val_acc:
            patience = 0 if skor_seleksi > best_val_acc else patience + 1
            best_val_acc = skor_seleksi
            torch.save(state, run_dir / "checkpoint_best.pth", _use_new_zipfile_serialization=False)
        else:
            patience += 1
            if patience >= t["early_stop_patience"]:
                print(f"[Stage2] Early stopping di epoch {epoch}")
                break

    best = torch.load(run_dir / "checkpoint_best.pth", map_location=device)
    Path(c["final_path"]).parent.mkdir(parents=True, exist_ok=True)
    torch.save(best, c["final_path"], _use_new_zipfile_serialization=False)
    print(f"[Stage2] Selesai. Kriteria={kriteria}  skor_terbaik={best_val_acc:.4f}  "
          f"epoch={best.get('epoch')}  val_acc_fusi={best.get('val_acc'):.4f}")
    print(f"[Stage2] Per mode pada epoch terpilih: {best.get('val_acc_per_mode')}")
    print(f"[Stage2] Disimpan ke {c['final_path']}")

    # --- Ablation #1: fusi vs RGB-saja vs termal-saja, di rffnet_val.csv ---
    rgb_encoder.load_state_dict(best["rgb_encoder"]); thermal_encoder.load_state_dict(best["thermal_encoder"])
    fusion.load_state_dict(best["fusion"]); head.load_state_dict(best["head_classification"])
    rgb_encoder.eval(); thermal_encoder.eval(); fusion.eval(); head.eval()
    modality_dropout.eval()  # [PATCH P2] tanpa ini, Ablation #1 dihitung dgn dropout aktif
    assert not modality_dropout.training, "modality_dropout masih di mode train"

    ablation_rows = []
    for mode_name, force_drop in [("fusi_penuh", None), ("rgb_saja", "thermal"), ("termal_saja", "rgb")]:
        correct, total = 0, 0
        with torch.no_grad():
            for rgb, thermal, seg, labels in val_loader:
                rgb, thermal, labels = rgb.to(device), thermal.to(device), labels.to(device)
                logits = _forward_full_model(rgb, thermal, rgb_encoder, thermal_encoder, modality_dropout,
                                              fusion, head, force_drop=force_drop)
                correct += (logits.argmax(-1) == labels).sum().item()
                total += rgb.size(0)
        acc = correct / total
        ablation_rows.append({"mode": mode_name, "accuracy": acc})
        print(f"[Stage2][Ablation1] {mode_name}: accuracy={acc:.4f}")

    fusion_acc = ablation_rows[0]["accuracy"]
    for row in ablation_rows[1:]:
        row["delta_m_vs_fusion"] = M.delta_m(fusion_acc, row["accuracy"])

    ablation_csv = Path(config["ablation1"]["output_csv"])
    ablation_csv.parent.mkdir(parents=True, exist_ok=True)
    import csv as csv_mod
    with open(ablation_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv_mod.DictWriter(f, fieldnames=["mode", "accuracy", "delta_m_vs_fusion"])
        writer.writeheader()
        for row in ablation_rows:
            writer.writerow(row)
    print(f"[Stage2] Ablation #1 disimpan ke {ablation_csv}")

    save_run_artifacts(config, run_dir, {"best_val_acc": best_val_acc, "ablation1": ablation_rows})


# =============================================================================
# Stage 4 -- Kurva degradasi terkontrol (evaluasi, bukan training baru)
# =============================================================================

def run_stage4(config: dict, device: torch.device):
    """Evaluasi fusion_v1.pth di berbagai level tau (smoke + degradasi termal),
    hasilkan reports/degradation_curve.csv + plot. TIDAK melatih bobot baru --
    dipakai membangun label supervisi (tau) untuk Stage 5.

    PENTING (bug diperbaiki, ditemukan lewat run nyata): versi sebelumnya menerapkan
    degradasi ke tensor yang SUDAH DINORMALISASI (T.Normalize), lalu "membalikkan"
    normalisasi dengan cara salah (kali 255 + clip 0-255) -- ini merusak gambar
    bahkan di tau=0.0 (nilai negatif hasil normalisasi ke-clip jadi 0/hitam).
    Terbukti dari: Ablation #1 Stage 2 di data bersih -> termal_saja=96.67%,
    tapi Stage 4 tau=0.0 (harusnya setara "bersih") -> cuma 25%. Sekarang gambar
    RAW (PIL, belum dinormalisasi) diambil LANGSUNG dari file, degradasi diterapkan
    di ruang piksel 0-255 yang benar, BARU dinormalisasi pakai T.Normalize resmi
    sebelum masuk model."""
    import csv as csv_mod
    import numpy as np
    from PIL import Image
    from torchvision import transforms as T
    from src.data.dataset_rffnet import RGB_MEAN, RGB_STD, THERMAL_MEAN, THERMAL_STD, parse_split_list

    d, mdl = config["data"], config["model"]
    deg = config["degradation"]
    out = config["output"]

    assert d["split"] == "val", "Bagian 3.8 #2: Stage 4 wajib pakai rffnet_val.csv, bukan test"

    rffnet_root = Path(d["rffnet_root"])
    img_dir = rffnet_root / "images"
    ids = parse_split_list(rffnet_root.parent / "lists" / f"{d['split']}_flm.txt")
    image_size = d["image_size"]

    rgb_norm = T.Normalize(RGB_MEAN, RGB_STD)
    thermal_norm = T.Normalize(THERMAL_MEAN, THERMAL_STD)

    rgb_encoder = RGBEncoder().to(device)
    thermal_encoder = ThermalEncoder().to(device)
    fusion = CrossAttentionFusion().to(device)
    head = ClassificationHead().to(device)

    ckpt = torch.load(mdl["checkpoint"], map_location=device)
    rgb_encoder.load_state_dict(ckpt["rgb_encoder"]); thermal_encoder.load_state_dict(ckpt["thermal_encoder"])
    fusion.load_state_dict(ckpt["fusion"]); head.load_state_dict(ckpt["head_classification"])
    rgb_encoder.eval(); thermal_encoder.eval(); fusion.eval(); head.eval()

    rows = []
    for tau in deg["tau_levels"]:
        correct_rgb = correct_thermal = correct_fusion = total = 0
        with torch.no_grad():
            for i, fid in enumerate(ids):
                # --- Load RAW (belum dinormalisasi) langsung dari file ---
                rgb_img = Image.open(img_dir / f"img_rgb_({fid}).png").convert("RGB").resize((image_size, image_size))
                thermal_img = Image.open(img_dir / f"img_ir_({fid}).png").convert("L").resize((image_size, image_size))
                gt_img = Image.open(img_dir / f"img_gt_({fid}).png").convert("L").resize((image_size, image_size), Image.NEAREST)

                rgb_np = np.array(rgb_img, dtype=np.uint8)          # (H,W,3) 0-255 -- RAW asli
                thermal_np = np.array(thermal_img, dtype=np.uint8)  # (H,W) 0-255 -- RAW asli

                # --- Degradasi di ruang piksel 0-255 yang BENAR ---
                rgb_degraded = inject_synthetic_smoke(rgb_np, tau=tau, seed=42 + i)
                thermal_degraded = degrade_thermal(thermal_np, tau=tau, seed=42 + i)

                # --- Normalisasi resmi (SETELAH degradasi, bukan sebelum) ---
                rgb_t = rgb_norm(torch.from_numpy(rgb_degraded / 255.0).permute(2, 0, 1).float())
                thermal_t = thermal_norm(torch.from_numpy(thermal_degraded / 255.0).unsqueeze(0).float())

                rgb_b = rgb_t.unsqueeze(0).to(device)
                thermal_b = thermal_t.unsqueeze(0).to(device)

                gt_arr = np.array(gt_img)
                has_fire = bool((gt_arr >= 190).any())    # kelas api (~255)
                has_smoke = bool(((gt_arr > 60) & (gt_arr < 190)).any())  # [PATCH P1] konjungsi PER PIKSEL
                label = 2 if (has_fire and has_smoke) else (1 if has_fire else 0)

                for mode, force_drop, counter_name in [
                    ("rgb", "thermal", "rgb"), ("thermal", "rgb", "thermal"), ("fusion", None, "fusion")
                ]:
                    r_tok, th_tok = rgb_encoder(rgb_b), thermal_encoder(thermal_b)
                    if force_drop == "rgb":
                        r_tok = torch.zeros_like(r_tok)
                    elif force_drop == "thermal":
                        th_tok = torch.zeros_like(th_tok)
                    fused = fusion(r_tok, th_tok)
                    pred = head(fused).argmax(-1).item()
                    if pred == label:
                        if counter_name == "rgb":
                            correct_rgb += 1
                        elif counter_name == "thermal":
                            correct_thermal += 1
                        else:
                            correct_fusion += 1
                total += 1

        row = {"tau": tau, "acc_rgb_only": correct_rgb / total, "acc_thermal_only": correct_thermal / total,
               "acc_fusion": correct_fusion / total}
        rows.append(row)
        print(f"[Stage4] tau={tau}: {row}")

    csv_path = Path(out["curve_csv"])
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv_mod.DictWriter(f, fieldnames=["tau", "acc_rgb_only", "acc_thermal_only", "acc_fusion"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[Stage4] Kurva degradasi disimpan ke {csv_path}")

    try:
        import matplotlib.pyplot as plt
        taus = [r["tau"] for r in rows]
        plt.figure(figsize=(7, 5))
        plt.plot(taus, [r["acc_rgb_only"] for r in rows], marker="o", label="RGB saja")
        plt.plot(taus, [r["acc_thermal_only"] for r in rows], marker="o", label="Termal saja")
        plt.plot(taus, [r["acc_fusion"] for r in rows], marker="o", label="Fusi", linewidth=2.5)
        plt.xlabel("tau (level degradasi)"); plt.ylabel("Akurasi klasifikasi")
        plt.title("Kurva degradasi -- ketahanan modalitas"); plt.legend(); plt.grid(alpha=0.3)
        Path(out["curve_plot"]).parent.mkdir(parents=True, exist_ok=True)  # WAJIB, jaga2 kalau beda folder dari curve_csv
        plt.savefig(out["curve_plot"], dpi=120, bbox_inches="tight")
        print(f"[Stage4] Plot disimpan ke {out['curve_plot']}")
    except ImportError:
        print("[Stage4] matplotlib tidak tersedia -- plot dilewati, CSV tetap tersimpan.")


# =============================================================================
# Stage 5 -- Reliability-gated fusion
# =============================================================================

def train_stage5(config: dict, device: torch.device):
    """Stage 5 -- Reliability-gated fusion. Melatih DualReliabilityGate supaya
    memprediksi skor keandalan (0-1) per modalitas, disupervisi regresi terhadap
    `1 - tau`.

    DESAIN (beda dari kerangka awal): TIDAK bergantung pada cache Stage 4 sama
    sekali -- dataset degradasi dibangun ON-THE-FLY langsung dari RFFNet raw,
    dengan LOGIKA SAMA yang sudah diperbaiki di run_stage4 (degradasi di ruang
    piksel 0-255 SEBELUM normalisasi, bukan sesudah). Ini menghindari satu lagi
    masalah transfer file besar antar-notebook Kaggle (checkpoint saja sudah
    berkali-kali kena auto-extract, cache tensor besar akan lebih parah lagi).

    Beda penting lain dari Stage 4: tau RGB dan tau termal disample SECARA
    INDEPENDEN per sampel (bukan satu tau yang sama utk keduanya) -- supaya gate
    belajar menilai keandalan tiap modalitas TERPISAH (skenario dunia nyata:
    asap cuma ganggu RGB, drift NUC cuma ganggu termal, jarang dua-duanya
    persis bareng)."""
    import random
    import numpy as np
    from PIL import Image
    from torchvision import transforms as T
    from src.data.dataset_rffnet import RGB_MEAN, RGB_STD, THERMAL_MEAN, THERMAL_STD, parse_split_list

    d, mdl, t, c = config["data"], config["model"], config["training"], config["checkpoint"]

    class Stage5DegradedDataset(Dataset):
        def __init__(self, split, root, image_size, seed):
            self.img_dir = root / "images"
            self.ids = parse_split_list(root.parent / "lists" / f"{split}_flm.txt")
            self.image_size = image_size
            self.rng = random.Random(seed)
            self.rgb_norm = T.Normalize(RGB_MEAN, RGB_STD)
            self.thermal_norm = T.Normalize(THERMAL_MEAN, THERMAL_STD)

        def __len__(self):
            return len(self.ids)

        def __getitem__(self, idx):
            fid = self.ids[idx]
            rgb_img = Image.open(self.img_dir / f"img_rgb_({fid}).png").convert("RGB").resize(
                (self.image_size, self.image_size))
            thermal_img = Image.open(self.img_dir / f"img_ir_({fid}).png").convert("L").resize(
                (self.image_size, self.image_size))
            rgb_np = np.array(rgb_img, dtype=np.uint8)
            thermal_np = np.array(thermal_img, dtype=np.uint8)

            tau_rgb = self.rng.uniform(0.0, 1.0)
            tau_thermal = self.rng.uniform(0.0, 1.0)
            seed_i = self.rng.randint(0, 1_000_000)

            rgb_degraded = inject_synthetic_smoke(rgb_np, tau=tau_rgb, seed=seed_i)
            thermal_degraded = degrade_thermal(thermal_np, tau=tau_thermal, seed=seed_i)

            rgb_t = self.rgb_norm(torch.from_numpy(rgb_degraded / 255.0).permute(2, 0, 1).float())
            thermal_t = self.thermal_norm(torch.from_numpy(thermal_degraded / 255.0).unsqueeze(0).float())
            return rgb_t, thermal_t, torch.tensor(tau_rgb, dtype=torch.float32), torch.tensor(tau_thermal, dtype=torch.float32)

    rffnet_root = Path(d["rffnet_root"])
    image_size = d.get("image_size", 224)
    train_set = Stage5DegradedDataset("train", rffnet_root, image_size, seed=config.get("seed", 42))
    val_set = Stage5DegradedDataset("val", rffnet_root, image_size, seed=config.get("seed", 42) + 1)
    train_loader = DataLoader(train_set, batch_size=t["batch_size"], shuffle=True, num_workers=4,
                               pin_memory=True, drop_last=True)
    val_loader = DataLoader(val_set, batch_size=t["batch_size"], shuffle=False, num_workers=4, pin_memory=True)
    print(f"[Stage5] Dataset on-the-fly siap: train={len(train_set)}  val={len(val_set)}")

    rgb_encoder = RGBEncoder(mdl["embedding_dim"]).to(device)
    thermal_encoder = ThermalEncoder(embedding_dim=mdl["embedding_dim"]).to(device)
    fusion = CrossAttentionFusion(dim=mdl["embedding_dim"]).to(device)
    head = ClassificationHead(in_dim=mdl["embedding_dim"] * 2).to(device)
    gate = DualReliabilityGate(mdl["embedding_dim"], mdl["gate_hidden_dim"], mdl["gate_shared_backbone"]).to(device)

    ckpt = torch.load(mdl["base_checkpoint"], map_location=device)
    rgb_encoder.load_state_dict(ckpt["rgb_encoder"]); thermal_encoder.load_state_dict(ckpt["thermal_encoder"])
    fusion.load_state_dict(ckpt["fusion"]); head.load_state_dict(ckpt["head_classification"])
    for module in (rgb_encoder, thermal_encoder, fusion, head):
        for p in module.parameters():
            p.requires_grad = False
        module.eval()
    print("[Stage5] Model dasar (Stage 2) dibekukan, hanya gate head yang dilatih.")

    optimizer = torch.optim.AdamW(gate.parameters(), lr=t["lr"], weight_decay=t["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t["epochs"])

    run_dir = Path(c["out_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)  # WAJIB -- torch.save() tidak auto-buat folder
    best_val_loss, patience = float("inf"), 0

    for epoch in range(1, t["epochs"] + 1):
        t0 = time.time()
        gate.train()
        train_loss = 0.0
        for rgb, thermal, tau_rgb, tau_thermal in train_loader:
            rgb, thermal = rgb.to(device), thermal.to(device)
            tau_rgb, tau_thermal = tau_rgb.to(device), tau_thermal.to(device)
            optimizer.zero_grad()
            with torch.no_grad():
                r_tok, th_tok = rgb_encoder(rgb), thermal_encoder(thermal)
            pred_rgb, pred_thermal = gate(r_tok, th_tok)
            loss = reliability_regression_loss(pred_rgb, pred_thermal, tau_rgb, tau_thermal)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * rgb.size(0)
        train_loss /= len(train_set)
        scheduler.step()

        gate.eval()
        val_loss = 0.0
        with torch.no_grad():
            for rgb, thermal, tau_rgb, tau_thermal in val_loader:
                rgb, thermal = rgb.to(device), thermal.to(device)
                tau_rgb, tau_thermal = tau_rgb.to(device), tau_thermal.to(device)
                r_tok, th_tok = rgb_encoder(rgb), thermal_encoder(thermal)
                pred_rgb, pred_thermal = gate(r_tok, th_tok)
                val_loss += reliability_regression_loss(pred_rgb, pred_thermal, tau_rgb, tau_thermal).item() * rgb.size(0)
        val_loss /= len(val_set)

        print(f"[Stage5] epoch {epoch}/{t['epochs']}  train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  ({time.time()-t0:.1f}s)")

        state = {"rgb_encoder": rgb_encoder.state_dict(), "thermal_encoder": thermal_encoder.state_dict(),
                 "fusion": fusion.state_dict(), "head_classification": head.state_dict(),
                 "gate": gate.state_dict(), "epoch": epoch, "val_loss": val_loss}

        if epoch % c.get("save_every_n_epochs", 2) == 0 or epoch == t["epochs"]:
            torch.save(state, run_dir / "checkpoint_last.pth", _use_new_zipfile_serialization=False)
        if val_loss < best_val_loss:
            best_val_loss, patience = val_loss, 0
            torch.save(state, run_dir / "checkpoint_best.pth", _use_new_zipfile_serialization=False)
        else:
            patience += 1
            if patience >= t["early_stop_patience"]:
                print(f"[Stage5] Early stopping di epoch {epoch}")
                break

    best = torch.load(run_dir / "checkpoint_best.pth", map_location=device, weights_only=False)
    Path(c["final_path"]).parent.mkdir(parents=True, exist_ok=True)
    torch.save(best, c["final_path"], _use_new_zipfile_serialization=False)
    print(f"[Stage5] Selesai. Best val_loss={best_val_loss:.4f}. Disimpan ke {c['final_path']}")

    # --- Ablation #2: dropout-saja (Stage 2) vs dropout+gating (Stage 5), sepanjang tau ---
    rgb_encoder.load_state_dict(best["rgb_encoder"]); thermal_encoder.load_state_dict(best["thermal_encoder"])
    fusion.load_state_dict(best["fusion"]); head.load_state_dict(best["head_classification"]); gate.load_state_dict(best["gate"])
    rgb_encoder.eval(); thermal_encoder.eval(); fusion.eval(); head.eval(); gate.eval()

    eval_rffnet_root = Path(d["rffnet_root"])
    eval_ids = parse_split_list(eval_rffnet_root.parent / "lists" / "val_flm.txt")
    img_dir = eval_rffnet_root / "images"
    rgb_norm_eval = T.Normalize(RGB_MEAN, RGB_STD)
    thermal_norm_eval = T.Normalize(THERMAL_MEAN, THERMAL_STD)

    ablation_rows = []
    for tau in [0.0, 0.3, 0.6, 1.0]:
        correct_no_gate, correct_with_gate, total = 0, 0, 0
        with torch.no_grad():
            for i, fid in enumerate(eval_ids):
                rgb_img = Image.open(img_dir / f"img_rgb_({fid}).png").convert("RGB").resize((image_size, image_size))
                thermal_img = Image.open(img_dir / f"img_ir_({fid}).png").convert("L").resize((image_size, image_size))
                gt_img = Image.open(img_dir / f"img_gt_({fid}).png").convert("L").resize((image_size, image_size), Image.NEAREST)

                rgb_degraded = inject_synthetic_smoke(np.array(rgb_img, dtype=np.uint8), tau=tau, seed=100 + i)
                thermal_degraded = degrade_thermal(np.array(thermal_img, dtype=np.uint8), tau=tau, seed=100 + i)
                rgb_b = rgb_norm_eval(torch.from_numpy(rgb_degraded / 255.0).permute(2, 0, 1).float()).unsqueeze(0).to(device)
                thermal_b = thermal_norm_eval(torch.from_numpy(thermal_degraded / 255.0).unsqueeze(0).float()).unsqueeze(0).to(device)

                gt_arr = np.array(gt_img)
                has_fire = bool((gt_arr >= 190).any())
                has_smoke = bool(((gt_arr > 60) & (gt_arr < 190)).any())  # [PATCH P1]
                label = 2 if (has_fire and has_smoke) else (1 if has_fire else 0)

                r_tok, th_tok = rgb_encoder(rgb_b), thermal_encoder(thermal_b)
                pred_no_gate = head(fusion(r_tok, th_tok)).argmax(-1).item()
                rgb_rel, thermal_rel = gate(r_tok, th_tok)
                pred_with_gate = head(fusion(r_tok, th_tok, rgb_rel, thermal_rel)).argmax(-1).item()

                correct_no_gate += int(pred_no_gate == label)
                correct_with_gate += int(pred_with_gate == label)
                total += 1
        ablation_rows.append({"tau": tau, "acc_no_gate": correct_no_gate / total, "acc_with_gate": correct_with_gate / total})
        print(f"[Stage5][Ablation2] tau={tau}: no_gate={correct_no_gate/total:.4f}  with_gate={correct_with_gate/total:.4f}")

    import csv as csv_mod
    ablation_csv = Path(config["ablation2"]["output_csv"])
    ablation_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(ablation_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv_mod.DictWriter(f, fieldnames=["tau", "acc_no_gate", "acc_with_gate"])
        writer.writeheader()
        writer.writerows(ablation_rows)
    print(f"[Stage5] Ablation #2 disimpan ke {ablation_csv}")

    save_run_artifacts(config, run_dir, {"best_val_loss": best_val_loss, "ablation2": ablation_rows})


# =============================================================================
# Stage 6 -- Localization (Jalur A: attention rollout, Jalur B: head segmentasi)
# =============================================================================

def attention_rollout_heatmap(attn_weights_per_layer: list, threshold_percentile: float = 90.0):
    """Jalur A -- gabungkan attention map dari tiap layer cross-attention jadi satu
    heatmap (rollout = perkalian matriks attention berurutan antar layer, teknik
    standar dari Abnar & Zuidema 2020). Tidak butuh label tambahan sama sekali.

    PENTING (bug diperbaiki): attn_weights_per_layer diasumsikan berbentuk
    (B, n_heads, N_q, N_kv) di versi awal fungsi ini, TAPI hasil capture nyata
    dari nn.MultiheadAttention (lewat forward hook, `need_weights` default True)
    SUDAH di-rata-ratakan antar head oleh PyTorch sendiri (`average_attn_weights=True`
    adalah default) -- jadi bentuk aslinya (B, N_q, N_kv), TANPA dimensi head.
    Kalau dipaksa `.mean(dim=1)` spt sebelumnya, itu keliru merata-ratakan dimensi
    N_q, bukan head -- bug diam-diam yang nggak keliatan dari shape output (sama-sama
    valid secara bentuk, tapi salah secara makna). Sekarang fungsi ini terima
    langsung list of (B, N_q, N_kv), tanpa averaging tambahan.

    attn_weights_per_layer: list of (B, N_q, N_kv) attention weight per layer,
    hasil capture lewat forward hook pada submodul nn.MultiheadAttention.
    """
    rollout = None
    for attn in attn_weights_per_layer:
        rollout = attn if rollout is None else torch.bmm(attn, rollout)
    heatmap = rollout.mean(dim=1)  # rata-rata query -> importance per posisi key, (B, N_kv)
    threshold = torch.quantile(heatmap, threshold_percentile / 100.0, dim=-1, keepdim=True)
    binary_heatmap = (heatmap >= threshold).float()
    return heatmap, binary_heatmap


def run_stage6(config: dict, device: torch.device):
    j_a, j_b = config["jalur_a_attention_rollout"], config["jalur_b_segmentation_head"]

    if j_b["enabled"]:
        d, mdl, c = config["data"], config["model"], config["checkpoint"]
        train_set, val_set, test_set = build_rffnet_datasets(Path(d["rffnet_root"]), with_mask=True,
                                                               image_size=d["image_size"])
        train_loader = DataLoader(train_set, batch_size=j_b["batch_size"], shuffle=True, num_workers=4,
                                   pin_memory=True, drop_last=True)
        val_loader = DataLoader(val_set, batch_size=j_b["batch_size"], shuffle=False, num_workers=4,
                                 pin_memory=True)

        rgb_encoder = RGBEncoder().to(device)
        thermal_encoder = ThermalEncoder().to(device)
        fusion = CrossAttentionFusion().to(device)
        seg_head = SegmentationHead(n_classes=3, image_size=d["image_size"]).to(device)

        ckpt = torch.load(mdl["base_checkpoint"], map_location=device)
        rgb_encoder.load_state_dict(ckpt["rgb_encoder"]); thermal_encoder.load_state_dict(ckpt["thermal_encoder"])
        fusion.load_state_dict(ckpt["fusion"])

        if j_b["freeze_encoder"]:
            for module in (rgb_encoder, thermal_encoder, fusion):
                for p in module.parameters():
                    p.requires_grad = False
            print("[Stage6][JalurB] Encoder+fusi dibekukan, hanya head segmentasi dilatih.")

        optimizer = torch.optim.AdamW(seg_head.parameters(), lr=j_b["lr"], weight_decay=j_b["weight_decay"])
        criterion = nn.CrossEntropyLoss()

        best_val_miou, patience = 0.0, 0
        run_dir = Path(c["out_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)  # WAJIB -- torch.save() tidak auto-buat folder
        for epoch in range(1, j_b["epochs"] + 1):
            t0 = time.time()
            rgb_encoder.eval(); thermal_encoder.eval(); fusion.eval(); seg_head.train()
            train_loss = 0.0
            for rgb, thermal, seg, has_obj in train_loader:
                rgb, thermal, seg = rgb.to(device), thermal.to(device), seg.to(device)
                optimizer.zero_grad()
                with torch.no_grad():
                    r_tok, th_tok = rgb_encoder(rgb), thermal_encoder(thermal)
                    fused = fusion(r_tok, th_tok)
                logits = seg_head(fused)
                loss = criterion(logits, seg)
                loss.backward()
                optimizer.step()
                train_loss += loss.item() * rgb.size(0)
            train_loss /= len(train_set)

            seg_head.eval()
            per_sample_iou = []
            with torch.no_grad():
                for rgb, thermal, seg, has_obj in val_loader:
                    rgb, thermal, seg = rgb.to(device), thermal.to(device), seg.to(device)
                    r_tok, th_tok = rgb_encoder(rgb), thermal_encoder(thermal)
                    fused = fusion(r_tok, th_tok)
                    pred = seg_head(fused).argmax(dim=1)
                    for b in range(pred.size(0)):
                        per_sample_iou.append(M.iou_per_class(pred[b], seg[b], n_classes=3))
            val_miou, _ = M.mean_iou(per_sample_iou)

            print(f"[Stage6][JalurB] epoch {epoch}/{j_b['epochs']}  train_loss={train_loss:.4f}  "
                  f"val_mIoU={val_miou:.4f}  ({time.time()-t0:.1f}s)")

            if val_miou > best_val_miou:
                best_val_miou, patience = val_miou, 0
                torch.save({"segmentation_head": seg_head.state_dict(), "epoch": epoch, "val_miou": val_miou},
                           run_dir / "checkpoint_best_segmentation.pth", _use_new_zipfile_serialization=False)
            else:
                patience += 1
                if patience >= j_b["early_stop_patience"]:
                    print(f"[Stage6][JalurB] Early stopping di epoch {epoch}")
                    break

        best = torch.load(run_dir / "checkpoint_best_segmentation.pth", map_location=device)
        out_path = Path(config["checkpoint"]["final_path_segmentation_head"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(best, out_path, _use_new_zipfile_serialization=False)
        print(f"[Stage6][JalurB] Selesai. Best val_mIoU={best_val_miou:.4f}. Disimpan ke {out_path}")

    if j_a["enabled"]:
        print("[Stage6][JalurA] attention_rollout_heatmap() siap dipanggil saat inference -- "
              "tidak ada training terpisah (weak supervision, tanpa label tambahan). "
              "Panggil fungsi ini di inference_service.py dgn attention weights dari forward pass fusion.")

    print("[Stage6] INGAT: evaluasi final (rffnet_test.csv, pointing-game/IoU, "
          "reports/ablation3_localization_weak_vs_full.csv) dilakukan SEKALI di "
          "src/evaluate.py, bukan di sini -- lihat Bagian 3.8 #2.")


# =============================================================================
# Stage 7 -- Regime suhu radiometrik & domain-gap + LoRA (stretch)
# =============================================================================

def run_stage7(config: dict, device: torch.device):
    which = config["run_which"]
    assert which in ("thermal_regime", "domain_gap_lora"), which

    if which == "domain_gap_lora":
        cfg = config["domain_gap_lora"]
        rgb_encoder = RGBEncoder().to(device)
        thermal_encoder = ThermalEncoder().to(device)
        fusion = CrossAttentionFusion().to(device)
        head = ClassificationHead().to(device)

        ckpt = torch.load(cfg["base_checkpoint"], map_location=device)
        rgb_encoder.load_state_dict(ckpt["rgb_encoder"]); thermal_encoder.load_state_dict(ckpt["thermal_encoder"])
        fusion.load_state_dict(ckpt["fusion"]); head.load_state_dict(ckpt["head_classification"])

        for module in (rgb_encoder, thermal_encoder, fusion, head):
            for p in module.parameters():
                p.requires_grad = False

        n_lora_layers = inject_lora_into_linear_layers(
            fusion, target_names=tuple(cfg["lora_target_layers"]), rank=cfg["lora_rank"], alpha=cfg["lora_alpha"]
        )
        n_trainable, n_total = count_trainable_parameters(fusion)
        print(f"[Stage7][LoRA] {n_lora_layers} layer diganti LoRALinear -- "
              f"{n_trainable}/{n_total} parameter trainable ({n_trainable/n_total*100:.2f}%)")

        print("[Stage7][LoRA] Kerangka adaptasi siap. Sambungkan FLAME3Dataset "
              "(src/data/dataset_flame3.py) + split_for_lora() di N in "
              f"{cfg['n_adapt_grid']} begitu data FLAME3 tersedia dari tim data.")
    else:
        print("[Stage7][ThermalRegime] Gunakan src/data/dataset_flame3.py::bin_by_temperature_percentile "
              "setelah FLAME3Dataset menghasilkan metadata suhu per sampel -- lihat docstring modul itu.")


# =============================================================================
# Dispatcher
# =============================================================================

STAGE_DISPATCH = {
    1: train_stage1,
    2: train_stage2,
    4: run_stage4,
    5: train_stage5,
    6: run_stage6,
    7: run_stage7,
}


def main():
    parser = argparse.ArgumentParser(description="Entry point training tim model, dispatch per stage.")
    parser.add_argument("--config", required=True, help="Path ke file .yaml di configs/")
    parser.add_argument("--seed", type=int, default=None,
                        help="[PATCH P8] override benih; keluaran diberi sufiks _s<seed>")
    parser.add_argument("--tag", type=str, default=None,
                        help="[PATCH P10] sufiks bebas untuk keluaran, mis. ENCLAMA. "
                             "Dipakai ketika dua run berbeda hanya pada hal yang TIDAK "
                             "tercermin di nama berkas, misalnya bobot awal encoder termal.")
    parser.add_argument("--p", type=float, default=None,
                        help="[PATCH P4] override modality_dropout_p (Stage 2). Keluaran diberi sufiks agar tidak saling menimpa.")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.p is not None:
        tag = f"p{args.p}".replace(".", "")
        config["training"]["modality_dropout_p"] = args.p
        config["checkpoint"]["out_dir"] = f"{config['checkpoint']['out_dir']}_{tag}"
        config["checkpoint"]["final_path"] = config["checkpoint"]["final_path"].replace(".pth", f"_{tag}.pth")
        if "ablation1" in config:
            config["ablation1"]["output_csv"] = config["ablation1"]["output_csv"].replace(".csv", f"_{tag}.csv")
        print(f"[main] override p={args.p}, keluaran diberi sufiks _{tag}")
    stage = config["stage"]
    assert stage in STAGE_DISPATCH, f"Stage {stage} tidak dikenali. Stage yg didukung: {list(STAGE_DISPATCH)}"

    if args.seed is not None:
        config["seed"] = args.seed
        tag_s = f"s{args.seed}"
        config["checkpoint"]["out_dir"] = f"{config['checkpoint']['out_dir']}_{tag_s}"
        config["checkpoint"]["final_path"] = config["checkpoint"]["final_path"].replace(".pth", f"_{tag_s}.pth")
        for kunci in ("ablation1", "ablation2"):
            if kunci in config and "output_csv" in config[kunci]:
                config[kunci]["output_csv"] = config[kunci]["output_csv"].replace(".csv", f"_{tag_s}.csv")
        print(f"[main] override seed={args.seed}, keluaran diberi sufiks _{tag_s}")

    if args.tag:
        # [PATCH P10] Pada RUN 2B, sembilan run encoder BARU dan tiga run encoder
        # LAMA memakai nama keluaran yang sama persis, karena identitas encoder
        # tidak ikut ke nama berkas. Run LAMA menimpa lebih dulu, penggantian nama
        # baru terjadi sesudahnya, sehingga seluruh hasil p=0,2 encoder BARU hilang
        # dari disk dan hanya tersisa di log. Sufiks ini menutup celah itu.
        config["checkpoint"]["out_dir"] = f"{config['checkpoint']['out_dir']}_{args.tag}"
        config["checkpoint"]["final_path"] = config["checkpoint"]["final_path"].replace(".pth", f"_{args.tag}.pth")
        for kunci in ("ablation1", "ablation2"):
            if kunci in config and "output_csv" in config[kunci]:
                config[kunci]["output_csv"] = config[kunci]["output_csv"].replace(".csv", f"_{args.tag}.csv")
        print(f"[main] tag={args.tag}, keluaran diberi sufiks _{args.tag}")

    kunci_benih(int(config.get("seed", 42)))   # [PATCH P8]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Menjalankan Stage {stage} (run_id={config.get('run_id')}) di device={device} ===")

    STAGE_DISPATCH[stage](config, device)


if __name__ == "__main__":
    main()
