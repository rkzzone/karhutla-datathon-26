# %% [markdown]
# # RUN 1 — Stage 1, pra-pelatihan ulang encoder termal
#
# **Ini run terpenting.** Semua run lain menunggu hasilnya, dan gerbang G1 di
# akhir menentukan apakah Skenario C dilanjutkan atau dibatalkan.
#
# ## Input yang harus dipasang
#
# | Dataset Kaggle | Isi |
# |---|---|
# | `kode-orang-a-patched` | kode yang sudah ditambal P1 sampai P5 |
# | `abangbuan/flame2-254p-rgb-thermal` | 53.451 pasang citra 254p |
# | `abangbuan/frame-pair-labels-txt` | `10) Frame Pair Labels.txt` |
# | `subhanirsyaduddien/data-orang-c` | manifest dan daftar eksklusi kebocoran |
#
# ## Pengaturan
# Accelerator **GPU T4 x2** · Internet **ON** · Persistence **Files only**
#
# ## Keluaran
# `thermal_encoder_pretrained.pth`, diunggah kemudian sebagai dataset `ckpt-thermal-p5`
#
# **Perkiraan 2 sampai 3 jam.**

# %% [markdown]
# ## Sel 1 — Temukan path sebenarnya

# %%
from pathlib import Path

INPUT = Path("/kaggle/input")

def cari_folder(nama_berkas_contoh, maks=6):
    """Cari folder yang memuat berkas dengan pola tertentu."""
    hasil = []
    for p in INPUT.rglob(nama_berkas_contoh):
        if p.parent not in hasil:
            hasil.append(p.parent)
        if len(hasil) >= maks:
            break
    return hasil

print("kandidat folder citra RGB 254p:")
for p in cari_folder("254p RGB Frame (1).jpg"):
    print("   ", p, "| jumlah:", len(list(p.glob("*.jpg"))))

print("\nkandidat berkas label:")
for p in INPUT.rglob("*Frame Pair Labels*.txt"):
    print("   ", p)

print("\nkandidat manifest:")
for nama in ["flame2_train.csv", "flame2_excluded_leakage.csv"]:
    for p in INPUT.rglob(nama):
        print("   ", p)

print("\nfolder kode:")
for p in INPUT.rglob("train.py"):
    print("   ", p.parent.parent)

# %% [markdown]
# ## Sel 2 — Salin kode dan sesuaikan config
#
# **Isi keempat variabel di bawah dengan hasil Sel 1.**
# `ROOT` adalah folder yang **langsung** memuat `254p RGB Images/`, bukan folder citranya sendiri.

# %%
LABELS   = "/kaggle/input/frame-pair-labels-txt/10) Frame Pair Labels.txt"
ROOT     = "/kaggle/input/flame2-254p-rgb-thermal"
MANIFEST = "/kaggle/input/data-orang-c/flame2_train.csv"
EXCLUDED = "/kaggle/input/data-orang-c/flame2_excluded_leakage.csv"
KODE     = "/kaggle/input/kode-orang-a-patched"

# %%
import shutil, pathlib, yaml, os

REPO = pathlib.Path("/kaggle/working/repo")
if REPO.exists():
    shutil.rmtree(REPO)
shutil.copytree(KODE, REPO)
os.chdir(REPO)
print("kode disalin ke", REPO)

for nama, jalur in [("labels", LABELS), ("root", ROOT),
                    ("manifest", MANIFEST), ("excluded", EXCLUDED)]:
    ada = pathlib.Path(jalur).exists()
    print(f"  {nama:9s} {'OK   ' if ada else 'HILANG'} {jalur}")
    assert ada, f"path {nama} tidak ditemukan, periksa Sel 1"

p = pathlib.Path("configs/stage1_pretrain_thermal.yaml")
cfg = yaml.safe_load(p.read_text())
cfg["data"].update({"labels_path": LABELS, "dataset_root": ROOT,
                    "manifest_path": MANIFEST, "excluded_csv": EXCLUDED})
cfg["training"]["batch_size"] = 128          # [P3] dua GPU, naikkan dari 64
cfg["run_id"] = "stage1_20260824_pretrain-thermal-p5"
cfg["checkpoint"]["out_dir"] = "runs/stage1_20260824_pretrain-thermal-p5"
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
print("\n" + p.read_text())

# %% [markdown]
# ## Sel 3 — Verifikasi sebelum membakar tiga jam GPU
#
# **Jangan lanjut bila ada satu saja yang meleset.**

# %%
import sys, importlib.util
import numpy as np
import torch

sys.path.insert(0, ".")
from src.data.dataset_flame2 import DEFAULT_VIDEO_FRAME_RANGES as R

DURASI = {1: 291, 2: 183, 3: 404, 4: 301, 5: 267, 6: 185, 7: 239}
total = sum(hi - lo for lo, hi in R.values())
v12 = sum(R[v][1] - R[v][0] for v in (1, 2))
fps = [(R[v][1] - R[v][0]) / DURASI[v] for v in R]

lolos = []
lolos.append(("total bingkai 53451", total == 53451, total))
lolos.append(("video 1+2 mendekati 13700", abs(v12 - 13700) <= 2, v12))
lolos.append(("fps efektif 26-31", 26 <= min(fps) and max(fps) <= 31,
              f"{min(fps):.2f}-{max(fps):.2f}"))

spec = importlib.util.spec_from_file_location("e", "src/eval_paper_metrics.py")
e = importlib.util.module_from_spec(spec); spec.loader.exec_module(e)
kasus = [(np.array([[0, 125], [255, 0]]), 2), (np.array([[0, 0], [255, 0]]), 1),
         (np.array([[0, 0], [0, 0]]), 0), (np.array([[0, 125], [125, 0]]), 0)]
label_ok = all(e.label_from_gt(a) == h for a, h in kasus)
lolos.append(("aturan label P1", label_ok, "4 kasus"))

n_gpu = torch.cuda.device_count()
lolos.append(("dua GPU terdeteksi", n_gpu == 2, n_gpu))

print(f"{'pemeriksaan':32s} {'status':8s} nilai")
print("-" * 60)
for nama, ok, nilai in lolos:
    print(f"{nama:32s} {'LOLOS' if ok else 'GAGAL':8s} {nilai}")

assert all(ok for _, ok, _ in lolos), "ADA PEMERIKSAAN GAGAL, jangan lanjut"
print("\nSemua lolos. Aman menjalankan Sel 4.")

# %% [markdown]
# ## Sel 4 — Jalankan Stage 1
#
# Perhatikan dua baris di awal keluaran:
# ```
# [P3] DataParallel aktif pada 2 GPU
# RGBEncoder: 22.1M total, 5.3M trainable
# ```
# Bila baris pertama tidak muncul, run akan dua kali lebih lama.

# %%
!python src/train.py --config configs/stage1_pretrain_thermal.yaml

# %% [markdown]
# ## Sel 5 — Gerbang G1, penentu lanjut atau berhenti
#
# **Dua pemeriksaan, bukan satu.** Versi pertama gerbang ini hanya menguji
# `val_acc > 0,70`, dan itu keliru: validasi berkelas tunggal lolos ambang itu
# secara trivial. Distribusi kelas diperiksa LEBIH DULU.

# %%
import json, torch, pathlib, yaml, sys
sys.path.insert(0, ".")

ck = torch.load("weights_final/thermal_encoder_pretrained.pth",
                map_location="cpu", weights_only=False)
val_acc = float(ck["val_acc"])
epoch = int(ck.get("epoch", -1))
MAYORITAS, ACUAN_LAMA = 0.476, 0.5148

# --- G1a: apakah validasi memuat lebih dari satu kelas? ---
# Distribusi dihitung ULANG di sini, bukan disalin tangan dari log Sel 4.
# Tidak ada citra yang dimuat, hanya label dan manifest, jadi selesai dalam
# hitungan detik. Ini menghilangkan satu langkah manual yang mudah terlupa.
from src.data.dataset_flame2 import (load_frame_labels_raw, load_flame2_manifest,
                                     load_excluded_ids, split_by_block,
                                     derive_class_label, DEFAULT_VIDEO_FRAME_RANGES)

_fl = load_frame_labels_raw(pathlib.Path(LABELS))
_mf = load_flame2_manifest(pathlib.Path(MANIFEST))
_ex = load_excluded_ids(pathlib.Path(EXCLUDED))
_fl = {k: v for k, v in _fl.items() if k not in _ex and k in _mf}

_cfg = yaml.safe_load(pathlib.Path('configs/stage1_pretrain_thermal.yaml').read_text())
_tr, _va, _vv = split_by_block(list(_fl.keys()), _fl, DEFAULT_VIDEO_FRAME_RANGES,
                               _cfg['data']['val_fraction'], _cfg['seed'])

DIST_VAL = {}
for _f in _va:
    _k = derive_class_label(_fl[_f]['fire'], _fl[_f]['smoke'])
    DIST_VAL[_k] = DIST_VAL.get(_k, 0) + 1

n_kelas = sum(1 for v in DIST_VAL.values() if v > 0)
n_val = sum(DIST_VAL.values())
mayoritas_val = max(DIST_VAL.values()) / n_val

print("G1a  distribusi kelas validasi")
print(f"     {DIST_VAL}")
print(f"     kelas hadir      : {n_kelas} dari 3")
print(f"     kelas terbanyak  : {mayoritas_val * 100:.1f}% dari validasi")
g1a = n_kelas >= 3 and mayoritas_val < 0.8
print(f"     status           : {'LOLOS' if g1a else 'GAGAL, val degeneratif'}")

# --- G1b: apakah akurasinya bermakna dibanding menebak kelas terbanyak? ---
print(f"\nG1b  val_acc = {val_acc:.4f} pada epoch {epoch}")
print(f"     menebak kelas terbanyak di validasi : {mayoritas_val:.4f}")
print(f"     acuan lama                          : {ACUAN_LAMA:.4f}")
print(f"     selisih thd tebakan terbanyak       : {(val_acc - mayoritas_val) * 100:+.2f} poin")
g1b = val_acc > mayoritas_val + 0.15
print(f"     status                              : {'LOLOS' if g1b else 'GAGAL'}")

# --- G1c: apakah checkpoint yang tersimpan sudah terlatih, bukan epoch awal? ---
print(f"\nG1c  epoch checkpoint tersimpan: {epoch}")
g1c = epoch >= 3
print(f"     status: {'LOLOS' if g1c else 'GAGAL, checkpoint terlalu awal, periksa P7'}")

print("\n" + "=" * 64)
if g1a and g1b and g1c:
    print("G1 LOLOS PENUH. Validasi memuat ketiga kelas, akurasinya jauh di atas")
    print("tebakan kelas terbanyak, dan checkpoint berasal dari epoch terlatih.")
    print("LANJUT ke RUN 2.")
elif not g1a:
    print("G1 GAGAL pada distribusi kelas. val_acc berapa pun TIDAK BERMAKNA.")
    print("Periksa apakah split_by_block (P6) benar-benar dipakai, bukan split_by_scene.")
elif not g1c:
    print("G1 GAGAL: checkpoint dari epoch terlalu awal. Pakai checkpoint_last.pth,")
    print("atau pastikan patch P7 aktif lalu jalankan ulang.")
else:
    print("G1 GAGAL pada akurasi. Model tidak jauh lebih baik dari menebak kelas")
    print("terbanyak. HENTIKAN Skenario C, kerjakan Skenario A saja.")
print("=" * 64)

# %% [markdown]
# ## Sel 6 — Simpan keluaran
#
# Unduh `stage1_hasil.zip`, lalu unggah `thermal_encoder_pretrained.pth`
# sebagai dataset Kaggle baru bernama **`ckpt-thermal-p5`** untuk dipakai RUN 2.

# %%
import shutil, os, pathlib

OUT = pathlib.Path("/kaggle/working/keluaran")
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
shutil.copytree("weights_final", OUT / "weights_final")
if pathlib.Path("runs").exists():
    shutil.copytree("runs", OUT / "runs")

shutil.make_archive("/kaggle/working/stage1_hasil", "zip", OUT)
print("stage1_hasil.zip :",
      round(os.path.getsize("/kaggle/working/stage1_hasil.zip") / 1024 ** 2, 1), "MB")
for p in sorted(OUT.rglob("*")):
    if p.is_file():
        print("  ", p.relative_to(OUT), round(p.stat().st_size / 1024 ** 2, 1), "MB")
