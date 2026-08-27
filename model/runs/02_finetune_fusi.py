# %% [markdown]
# # RUN 2 — Stage 2 dengan sapuan p, menutup Ablation #3
#
# Ablation #3 dijanjikan di concept paper tetapi **tidak pernah dijalankan**:
# `train.py:218` versi lama hanya mengambil indeks tengah dari grid. Run ini
# menutupnya.
#
# ## Input yang harus dipasang
#
# | Dataset Kaggle | Isi | Catatan |
# |---|---|---|
# | `kode-orang-a-patched` | kode tertambal | |
# | `ckpt-thermal-p5` | hasil RUN 1 | unggah dulu dari `stage1_hasil.zip` |
# | `abangbuan/flame2` | **data RFFNet**, bukan FLAME 2 | jebakan penamaan, lihat Sel 1 |
# | `ckpt-thermal-lama` | encoder termal versi LAMA | untuk perbandingan A/B, lihat Sel 6 |
#
# ## Pengaturan
# Accelerator **GPU T4 x2** · Internet **ON**
#
# ## Keluaran
# `fusion_v1_p01.pth`, `_p02`, `_p03` beserta CSV Ablation #1 masing-masing
#
# **Perkiraan 45 sampai 60 menit.**

# %% [markdown]
# ## Sel 1 — Temukan data RFFNet
#
# Dataset bernama `flame2` tetapi isinya anotasi RFFNet. Penanda yang benar
# adalah keberadaan `img_gt_*.png`; FLAME 2 mentah tidak punya mask sama sekali.

# %%
from pathlib import Path

RFFNET = None
for gt in Path("/kaggle/input").rglob("img_gt_*.png"):
    root = gt.parent.parent                 # .../FLAME2
    lists = root.parent / "lists"
    n_gt = len(list((root / "images").glob("img_gt_*.png")))
    n_rgb = len(list((root / "images").glob("img_rgb_*.png")))
    flm = sorted(p.name for p in lists.glob("*_flm.txt")) if lists.is_dir() else []
    print("root  :", root)
    print("gt    :", n_gt, "| rgb:", n_rgb)
    print("lists :", flm or "TIDAK ADA, struktur folder berbeda")
    RFFNET = str(root)
    break

assert RFFNET, "data RFFNet tidak ditemukan, pastikan dataset abangbuan/flame2 terpasang"
print("\nRFFNET =", RFFNET)

# %% [markdown]
# ## Sel 2 — Salin kode, pasang checkpoint Stage 1, sesuaikan config

# %%
# Path dicari otomatis, tidak perlu disunting. Kaggle memasang dataset di
# /kaggle/input/datasets/<pemilik>/<slug>/ sehingga prefiksnya mudah keliru.
def _cari(pola, wajib=True, nama=''):
    # urut MENURUN supaya versi tertinggi menang, mis. v3 di atas v2
    hasil = sorted(Path('/kaggle/input').rglob(pola), reverse=True)
    if not hasil:
        if wajib:
            raise FileNotFoundError(f'{nama or pola} tidak ditemukan di /kaggle/input')
        return None
    if len(hasil) > 1:
        print(f'  PERINGATAN: {pola} ditemukan {len(hasil)}x, dipakai yang pertama')
        for h in hasil:
            print('     ', h)
    return str(hasil[0])

KODE = str(Path(_cari('src/train.py', nama='folder kode')).parent.parent)
CKPT_TERMAL = _cari('thermal_encoder_pretrained.pth', nama='encoder termal BARU')
CKPT_TERMAL_LAMA = _cari('thermal_encoder_LAMA_legacy.pth', wajib=False)

print('KODE             =', KODE)
print('CKPT_TERMAL      =', CKPT_TERMAL)
print('CKPT_TERMAL_LAMA =', CKPT_TERMAL_LAMA or 'TIDAK ADA, sel A/B akan dilewati')

# Pastikan yang terpasang adalah hasil RUN 1 versi v3, bukan run sebelumnya.
import torch as _t
_ck = _t.load(CKPT_TERMAL, map_location='cpu', weights_only=False)
print(f"\nencoder BARU: epoch {_ck.get('epoch')}, val_acc {float(_ck.get('val_acc')):.4f}")
assert float(_ck.get('val_acc')) < 0.99, (
    'val_acc mendekati 1,0 berarti ini checkpoint dari run split per-video yang '
    'degeneratif, bukan hasil RUN 1 v3. Unggah ulang stage1_hasil.zip yang benar.')
assert int(_ck.get('epoch', 0)) >= 3, 'checkpoint dari epoch terlalu awal, periksa P7'

# %%
import shutil, pathlib, yaml, os

REPO = pathlib.Path("/kaggle/working/repo")
if REPO.exists():
    shutil.rmtree(REPO)
shutil.copytree(KODE, REPO)
os.chdir(REPO)

# PENJAGA: pastikan kode yang tersalin memuat P6, bukan versi lama.
_ds = pathlib.Path('src/data/dataset_flame2.py').read_text(encoding='utf-8')
assert 'def split_by_block' in _ds, (
    'Kode yang tersalin BELUM memuat P6 (split blok terstratifikasi). '
    'Kemungkinan yang terpasang dataset kode versi lama. Lepas dataset v2 '
    'dari Input notebook, sisakan hanya v3.')
assert '[PATCH P7]' in pathlib.Path('src/train.py').read_text(encoding='utf-8'), (
    'Kode belum memuat P7, periksa versi dataset kode.')
print('penjaga kode: P6 dan P7 terdeteksi, versi benar')

pathlib.Path("weights_final").mkdir(exist_ok=True)
assert pathlib.Path(CKPT_TERMAL).exists(), "checkpoint Stage 1 tidak ditemukan"
shutil.copy(CKPT_TERMAL, "weights_final/thermal_encoder_pretrained.pth")

import torch
ck = torch.load("weights_final/thermal_encoder_pretrained.pth",
                map_location="cpu", weights_only=False)
print(f"checkpoint Stage 1 dimuat: epoch {ck.get('epoch')}, val_acc {ck.get('val_acc'):.4f}")
assert "module." not in list(ck["thermal_encoder"].keys())[0], \
    "kunci masih berprefiks 'module.', buka_dp tidak dipakai saat menyimpan"

p = pathlib.Path("configs/stage2_finetune_fusion.yaml")
cfg = yaml.safe_load(p.read_text())
cfg["data"]["rffnet_root"] = RFFNET
cfg["run_id"] = "stage2_20260824_finetune-fusion"
cfg["checkpoint"]["out_dir"] = "runs/stage2_20260824_finetune-fusion"
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
print("\n" + p.read_text())

# %% [markdown]
# ## Sel 3 — Verifikasi cepat

# %%
import sys
sys.path.insert(0, ".")
from src.data.dataset_rffnet import parse_split_list

for split in ["train", "val", "test"]:
    ids = parse_split_list(pathlib.Path(RFFNET).parent / "lists" / f"{split}_flm.txt")
    print(f"  {split:6s} {len(ids)} indeks")

print("\nharus: train 552, val 240, test 200")
print("GPU:", torch.cuda.device_count())

# %% [markdown]
# ## Sel 4 — Jalankan tiga nilai p
#
# Setiap run memberi sufiks otomatis pada keluarannya, jadi tidak saling menimpa.

# %%
for P in ["0.1", "0.2", "0.3"]:
    print("\n" + "=" * 62)
    print(f"  p = {P}")
    print("=" * 62)
    !python src/train.py --config configs/stage2_finetune_fusion.yaml --p {P}

# %% [markdown]
# ## Sel 5 — Gerbang G2 dan tabel Ablation #3
#
# Syarat lolos: baris `fusi_penuh` **tidak boleh lebih rendah** dari `rgb_saja`.
# Bila masih, P2 tidak aktif dan hasilnya tidak dapat dipakai.

# %%
import csv, pathlib

print(f"{'p':>5s} {'fusi':>8s} {'RGB':>8s} {'termal':>8s}  status")
print("-" * 48)
ringkasan = {}
for tag, p_val in [("p01", 0.1), ("p02", 0.2), ("p03", 0.3)]:
    f = pathlib.Path(f"reports/ablation1_unimodal_vs_fusion_{tag}.csv")
    if not f.exists():
        print(f"{p_val:5.1f}  berkas tidak ada")
        continue
    baris = {r["mode"]: float(r["accuracy"]) for r in csv.DictReader(open(f, encoding="utf-8"))}
    ok = baris["fusi_penuh"] >= baris["rgb_saja"]
    ringkasan[tag] = baris
    print(f"{p_val:5.1f} {baris['fusi_penuh']:8.4f} {baris['rgb_saja']:8.4f} "
          f"{baris['termal_saja']:8.4f}  {'LOLOS' if ok else 'GAGAL, P2 tidak aktif'}")

print("\nCatatan: akurasi bersih kemungkinan besar berimpit di ketiga p, karena")
print("tolok ukur ini sudah terbukti jenuh. Pembeda antar-p baru terlihat pada")
print("KURVA DEGRADASI di RUN 3, dan itulah isi Ablation #3 yang sebenarnya.")

# %% [markdown]
# ## Sel 6 — Perbandingan A/B, encoder termal lama melawan baru
#
# **Ini sel terpenting untuk slide.** `val_acc` Stage 1 lama (0,5148) dan baru
# (0,9758) diukur pada protokol validasi yang BERBEDA, sehingga tidak sebanding
# dan tidak boleh disandingkan begitu saja.
#
# Perbandingan yang sah: jalankan Stage 2 dengan protokol yang sama persis,
# hanya berganti encoder termal. Selisih di sinilah bukti bahwa perbaikan
# split pra-pelatihan benar-benar berdampak.

# %%
import pathlib, shutil, csv, torch

PUNYA_LAMA = pathlib.Path(CKPT_TERMAL_LAMA).exists()
print("encoder lama tersedia:", PUNYA_LAMA)

if PUNYA_LAMA:
    ck_lama = torch.load(CKPT_TERMAL_LAMA, map_location="cpu", weights_only=False)
    print(f"  lama : epoch {ck_lama.get('epoch')}, val_acc {float(ck_lama.get('val_acc')):.4f}")
    ck_baru = torch.load("weights_final/thermal_encoder_pretrained.pth",
                         map_location="cpu", weights_only=False)
    print(f"  baru : epoch {ck_baru.get('epoch')}, val_acc {float(ck_baru.get('val_acc')):.4f}")

    # simpan encoder baru, pasang yang lama, jalankan Stage 2 pada p yang sama
    shutil.copy("weights_final/thermal_encoder_pretrained.pth",
                "weights_final/thermal_encoder_BARU.pth")
    shutil.copy(CKPT_TERMAL_LAMA, "weights_final/thermal_encoder_pretrained.pth")
    print("\nencoder LAMA dipasang, menjalankan Stage 2 pembanding pada p=0.2 ...")
    !python src/train.py --config configs/stage2_finetune_fusion.yaml --p 0.2

    # kembalikan encoder baru dan beri nama berbeda pada keluaran pembanding
    for asal, tujuan in [("weights_final/fusion_v1_p02.pth", "weights_final/fusion_v1_p02_ENCLAMA.pth"),
                         ("reports/ablation1_unimodal_vs_fusion_p02.csv",
                          "reports/ablation1_unimodal_vs_fusion_p02_ENCLAMA.csv")]:
        if pathlib.Path(asal).exists():
            shutil.move(asal, tujuan)
    shutil.copy("weights_final/thermal_encoder_BARU.pth",
                "weights_final/thermal_encoder_pretrained.pth")
    print("\nencoder BARU dikembalikan, menjalankan Stage 2 pada p=0.2 ...")
    !python src/train.py --config configs/stage2_finetune_fusion.yaml --p 0.2
else:
    print("Dilewati. Unggah thermal_encoder_LAMA_legacy.pth sebagai dataset "
          "'ckpt-thermal-lama' bila ingin klaim A/B yang dapat dipertahankan.")

# %%
if PUNYA_LAMA:
    print(f"{'encoder termal':>16s} {'fusi':>8s} {'RGB':>8s} {'termal':>8s}")
    print("-" * 46)
    for nama, berkas in [("LAMA (0,5148)", "reports/ablation1_unimodal_vs_fusion_p02_ENCLAMA.csv"),
                         ("BARU (0,9758)", "reports/ablation1_unimodal_vs_fusion_p02.csv")]:
        f = pathlib.Path(berkas)
        if not f.exists():
            print(f"{nama:>16s}  berkas tidak ada")
            continue
        b = {r["mode"]: float(r["accuracy"]) for r in csv.DictReader(open(f, encoding="utf-8"))}
        print(f"{nama:>16s} {b['fusi_penuh']:8.4f} {b['rgb_saja']:8.4f} {b['termal_saja']:8.4f}")

    print("\nYang paling menentukan adalah kolom 'termal', karena hanya jalur itu")
    print("yang langsung bergantung pada encoder termal. Bila termal-saja naik")
    print("berarti perbaikan split pra-pelatihan terbukti berdampak hilir.")
    print("Bila tidak berubah, laporkan apa adanya: perbaikan itu membuat val_acc")
    print("Stage 1 dapat ditafsirkan, tetapi tidak mengubah performa hilir.")
    print("\nBandingkan juga kurva degradasinya di RUN 3, bukan akurasi bersih saja.")

# %% [markdown]
# ## Sel 7 — Simpan keluaran
#
# Unggah `stage2_hasil.zip` sebagai dataset **`ckpt-fusion-sweep`** untuk RUN 3.

# %%
import shutil, os

OUT = pathlib.Path("/kaggle/working/keluaran")
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
shutil.copytree("weights_final", OUT / "weights_final")
shutil.copytree("reports", OUT / "reports")
if pathlib.Path("runs").exists():
    shutil.copytree("runs", OUT / "runs")

shutil.make_archive("/kaggle/working/stage2_hasil", "zip", OUT)
print("stage2_hasil.zip :",
      round(os.path.getsize("/kaggle/working/stage2_hasil.zip") / 1024 ** 2, 1), "MB")
for p in sorted((OUT / "weights_final").glob("*.pth")):
    print("  ", p.name, round(p.stat().st_size / 1024 ** 2, 1), "MB")
