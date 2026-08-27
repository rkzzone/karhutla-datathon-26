#!/usr/bin/env python
"""RFFNet di bawah degradasi modalitas termal.

KENAPA INI EKSPERIMEN PALING PENTING YANG TERSISA
-------------------------------------------------
Pada kondisi bersih kita KALAH telak pada mIoU: 0,5328 melawan 0,8817. Itu wajar,
karena segmentasi adalah tujuan utama RFFNet dan keluaran sekunder bagi kami.

Tetapi RFFNet tidak punya mekanisme ketahanan modalitas sama sekali. Kami sudah
punya angka sendiri: kehilangan modalitas termal sepenuhnya berbiaya sekitar 5
poin akurasi pada partisi uji. Yang belum ada adalah angka pembandingnya.

Bila RFFNet jatuh jauh lebih dalam, ini satu slide yang memenangkan argumen:
kami kalah pada segmentasi kondisi bersih, tetapi menangani mode kegagalan yang
tidak ditangani baseline sama sekali. Bila RFFNet ternyata juga tahan, laporkan
apa adanya, dan klaim ketahanan kami harus dilemahkan. Kedua hasil layak.

CARA PAKAI
----------
Jalankan dari DALAM folder root repo RFFNet, sama seperti run_stage3_baseline.py:

    cd data_prep/raw/rffnet
    python /path/ke/run_baseline_degradasi.py \
        --yaml-file <sama seperti baseline> \
        --checkpoint weights/robo_fire_best.pth \
        --degradasi-src /path/ke/REVIEW_ORANG_A/kode/src \
        --tau 0.0 1.0 \
        --out /path/ke/baseline_eval/reports/baseline_degradasi.csv

Biaya: 200 sampel x 2221 ms x jumlah tau. Dua level sekitar 15 menit, CPU saja.

CATATAN KESETARAAN
------------------
Degradasi memakai degrade_thermal() yang SAMA PERSIS dengan yang dipakai untuk
mengukur model kami. Kalau tidak sama, perbandingannya tidak sah. Itu sebabnya
skrip ini mengimpornya dari kode tim model, bukan menulis ulang.
"""
import argparse
import csv
import io
import statistics
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # cegah plt.show() di test.py membuka window dan menggantung

import numpy as np
import torch
import yaml


def muat_config(yaml_file: str, checkpoint: str, device: str) -> dict:
    p = Path("config") / yaml_file
    if not p.exists():
        sys.exit(f"[ERROR] {p} tidak ada. Jalankan dari root repo RFFNet.")
    with open(p, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    config["PRETRAINED"] = None
    config["CHECKPOINT"] = checkpoint
    config["DEVICE"] = device
    return config


def cari_tensor_termal(batch):
    """Temukan tensor termal di dalam batch, apa pun bentuk strukturnya.

    Repo RFFNet memberi batch berisi RGB dan IR. Bentuk persisnya tidak
    didokumentasikan, jadi dideteksi: tensor 4 dimensi dengan 1 kanal, atau
    tensor kedua bila keduanya 3 kanal.
    """
    if isinstance(batch, dict):
        for k in ("ir", "thermal", "IR", "Thermal", "t"):
            if k in batch and torch.is_tensor(batch[k]):
                return ("dict", k)
        kandidat = [k for k, v in batch.items()
                    if torch.is_tensor(v) and v.dim() == 4 and v.shape[1] == 1]
        if len(kandidat) == 1:
            return ("dict", kandidat[0])
        sys.exit(f"[ERROR] Tidak dapat menentukan tensor termal. Kunci: {list(batch)}")

    if isinstance(batch, (list, tuple)):
        gambar = [i for i, v in enumerate(batch) if torch.is_tensor(v) and v.dim() == 4]
        satu_kanal = [i for i in gambar if batch[i].shape[1] == 1]
        if len(satu_kanal) == 1:
            return ("seq", satu_kanal[0])
        if len(gambar) >= 2:
            print(f"[PERINGATAN] Tidak ada tensor satu kanal. Memakai tensor gambar "
                  f"KEDUA (indeks {gambar[1]}, bentuk {tuple(batch[gambar[1]].shape)}) "
                  f"sebagai termal. PERIKSA INI sebelum melaporkan angkanya.")
            return ("seq", gambar[1])
        sys.exit("[ERROR] Batch tidak memuat dua tensor gambar.")

    sys.exit(f"[ERROR] Tipe batch tidak dikenali: {type(batch)}")


def degradasi_tensor(t: torch.Tensor, tau: float, degrade_thermal, mulai_seed: int):
    """Terapkan degrade_thermal() per sampel, di ruang piksel, lalu kembalikan tensor."""
    if tau == 0.0:
        return t
    keluar = t.clone()
    for i in range(t.shape[0]):
        kanal = t[i]                                   # (C, H, W)
        for c in range(kanal.shape[0]):
            arr = kanal[c].detach().cpu().numpy()
            lo, hi = float(arr.min()), float(arr.max())
            rentang = hi - lo if hi > lo else 1.0
            u8 = ((arr - lo) / rentang * 255.0).clip(0, 255).astype(np.uint8)
            rusak = degrade_thermal(u8, tau=tau, seed=mulai_seed + i)
            balik = rusak.astype(np.float32) / 255.0 * rentang + lo
            keluar[i, c] = torch.from_numpy(balik).to(t.dtype).to(t.device)
    return keluar


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yaml-file", required=True)
    ap.add_argument("--checkpoint", default="weights/robo_fire_best.pth")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda", "cuda:0"])
    ap.add_argument("--degradasi-src", required=True,
                    help="Path ke REVIEW_ORANG_A/kode/src, sumber degrade_thermal()")
    ap.add_argument("--tau", nargs="+", type=float, default=[0.0, 1.0])
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--out", type=Path, default=Path("reports/baseline_degradasi.csv"))
    a = ap.parse_args()

    sys.path.insert(0, str(Path(a.degradasi_src).resolve()))
    try:
        from augmentation.thermal_degradation import degrade_thermal
    except ImportError as e:
        sys.exit(f"[ERROR] Gagal impor degrade_thermal dari {a.degradasi_src}: {e}\n"
                 f"Harus memakai fungsi yang SAMA dengan yang dipakai model kami, "
                 f"kalau tidak perbandingannya tidak sah.")
    print(f"[INFO] degrade_thermal diimpor dari {a.degradasi_src}")

    try:
        from utils.training_tools import get_dataset, get_model, Trainer
        from utils.logger import Logger
        import test as rffnet_test_module
    except ImportError as e:
        sys.exit(f"[ERROR] Gagal impor modul repo RFFNet: {e}\n"
                 f"Jalankan dari DALAM folder root repo RFFNet.")

    config = muat_config(a.yaml_file, a.checkpoint, a.device)
    _, _, test_dataset = get_dataset(config, True)
    print(f"[INFO] {len(test_dataset)} sampel di test_dataset (lists/test_flm.txt)")

    baris = []
    for tau in a.tau:
        print("\n" + "=" * 62)
        print(f"  RFFNet pada tau = {tau}")
        print("=" * 62)

        model = get_model(config)
        logger = Logger(config)
        trainer = Trainer(config, model, len(test_dataset), test=True)

        asli = trainer.test_step
        latensi, lokasi = [], {}

        def test_step_terdegradasi(batch):
            if not lokasi:
                jenis, kunci = cari_tensor_termal(batch)
                lokasi["jenis"], lokasi["kunci"] = jenis, kunci
                bentuk = (batch[kunci] if jenis == "seq" else batch[kunci]).shape
                print(f"[INFO] Tensor termal: {jenis}[{kunci}], bentuk {tuple(bentuk)}")
            jenis, kunci = lokasi["jenis"], lokasi["kunci"]
            if jenis == "seq":
                batch = list(batch)
                batch[kunci] = degradasi_tensor(batch[kunci], tau, degrade_thermal, a.seed)
            else:
                batch = dict(batch)
                batch[kunci] = degradasi_tensor(batch[kunci], tau, degrade_thermal, a.seed)
            t0 = time.perf_counter()
            hasil = asli(batch)
            if str(config["DEVICE"]).startswith("cuda"):
                torch.cuda.synchronize()
            latensi.append((time.perf_counter() - t0) * 1000)
            return hasil

        trainer.test_step = test_step_terdegradasi

        buf = io.StringIO()
        with redirect_stdout(buf):
            metrik = rffnet_test_module.test(trainer, test_dataset, config, logger)
        teks = buf.getvalue()
        print(teks[-1500:])

        def ambil(*nama):
            if isinstance(metrik, dict):
                for n in nama:
                    if n in metrik:
                        return float(metrik[n])
            for n in nama:
                for ln in teks.splitlines():
                    if n.lower() in ln.lower() and ":" in ln:
                        try:
                            return float(ln.split(":")[-1].strip().split()[0])
                        except ValueError:
                            pass
            return None

        r = {
            "model": "RFFNet (robo_fire_best.pth)",
            "tau_termal": tau,
            "miou": ambil("val miou", "miou"),
            "recall": ambil("val avg_recall", "avg_recall"),
            "f1": ambil("val avg_f1", "avg_f1"),
            "iou_fire": ambil("val iou fire", "iou fire"),
            "iou_smoke": ambil("val iou smoke", "iou smoke"),
            "median_latency_ms": statistics.median(latensi) if latensi else None,
            "n_sampel": len(test_dataset),
        }
        baris.append(r)
        print(f"\n[HASIL] tau={tau}  mIoU={r['miou']}  recall={r['recall']}")

    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(baris[0].keys()))
        w.writeheader()
        w.writerows(baris)
    print(f"\n-> {a.out}")

    print("\n" + "=" * 62)
    print("PEMBACAAN")
    print("=" * 62)
    bersih = next((b for b in baris if b["tau_termal"] == 0.0), None)
    rusak = next((b for b in baris if b["tau_termal"] == 1.0), None)
    if bersih and rusak and bersih["miou"] and rusak["miou"]:
        turun = (bersih["miou"] - rusak["miou"]) * 100
        print(f"mIoU RFFNet: {bersih['miou']*100:.2f} -> {rusak['miou']*100:.2f}  "
              f"turun {turun:.2f} poin")
        print("Pembanding kami: akurasi klasifikasi turun sekitar 5 poin saat")
        print("modalitas termal hilang sepenuhnya.")
        print()
        print("PERINGATAN KESETARAAN: mIoU segmentasi dan akurasi klasifikasi")
        print("BUKAN metrik yang sama. Yang boleh dibandingkan adalah BESAR")
        print("PENURUNAN RELATIF terhadap kondisi bersih masing-masing, dan itu")
        print("pun harus dinyatakan sebagai perbandingan kasar, bukan setara.")
        rel = turun / (bersih["miou"] * 100) * 100
        print(f"\nPenurunan relatif RFFNet : {rel:.1f} persen dari nilai bersihnya")
        print(f"Penurunan relatif kami   : sekitar 5,5 persen (4,67 dari 85,00)")
    else:
        print("Metrik tidak lengkap. Periksa keluaran test.py di atas.")


if __name__ == "__main__":
    main()
