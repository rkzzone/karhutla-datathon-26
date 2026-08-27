# %% [markdown]
# # RUN 5 — Stage 6, lokalisasi dua jalur
#
# Jalur A attention rollout tanpa label piksel, Jalur B head segmentasi dengan
# label piksel.
#
# ## PERINGATAN SPLIT UJI
#
# Stage ini menyentuh `rffnet_test.csv`. Split itu sudah dibuka **dua kali**
# sebelumnya, dan run ini menjadi yang **ketiga**. Model tidak berubah di antara
# pembukaan, sehingga masih dapat dipertahankan, tetapi **catat dan nyatakan apa
# adanya bila juri bertanya**. Jangan biarkan itu terungkap dari pihak lain.
#
# ## Input, persis tiga
#
# | Dataset Kaggle | Isi | Penanda |
# |---|---|---|
# | `kode-orang-a-patched-v5` | kode dengan P9 dan P10 | `src/train.py` |
# | `ckpt-fusion-gated` | zip RUN 4 (`stage5_hasil.zip`) | `fusion_v2_gated.pth` |
# | `abangbuan/flame2` | anotasi RFFNet | `img_gt_*.png` |
#
# **Lepas `kode-orang-a-patched-v3`/`v4`** bila masih terpasang. Sel 1 menolak
# bila versi kode tidak memuat P9 dan P10.
#
# ## Keluaran
# `segmentation_head_v1.pth` · `fusion_v3_localization.pth` ·
# `ablation3_localization_weak_vs_full.csv`
#
# **Perkiraan 30 sampai 45 menit.**

# %% [markdown]
# ## Sel 1 — Path

# %%
from pathlib import Path

RFFNET = None
for gt in Path("/kaggle/input").rglob("img_gt_*.png"):
    RFFNET = str(gt.parent.parent)
    break
assert RFFNET, "data RFFNet tidak ditemukan"

def _cari(pola, wajib=True, nama=''):
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

_tr = Path(KODE, "src", "train.py").read_text(encoding="utf-8")
for penanda in ("[PATCH P9]", "[PATCH P10]"):
    assert penanda in _tr, (
        f"{penanda} tidak ada di {KODE}/src/train.py. Dataset kode versi lama "
        "masih terpasang. Lepas v3/v4, sisakan hanya kode-orang-a-patched-v5.")
print("penjaga kode: P9 dan P10 terdeteksi")

GATED = "/kaggle/input/ckpt-fusion-gated"
_kandidat = sorted(Path(GATED).rglob("fusion_v2_gated.pth"))
assert _kandidat, f"fusion_v2_gated.pth tidak ada di {GATED}. Pasang zip RUN 4."
CKPT = _kandidat[0]
print("RFFNET =", RFFNET)
print("CKPT   =", CKPT)

# %% [markdown]
# ## Sel 2 — Salin dan sesuaikan config

# %%
import shutil, pathlib, yaml, os, torch

REPO = pathlib.Path("/kaggle/working/repo")
if REPO.exists():
    shutil.rmtree(REPO)
shutil.copytree(KODE, REPO)
os.chdir(REPO)

pathlib.Path("weights_final").mkdir(exist_ok=True)
shutil.copy(CKPT, "weights_final/fusion_v2_gated.pth")
ck = torch.load("weights_final/fusion_v2_gated.pth", map_location="cpu", weights_only=False)
print("kunci checkpoint:", list(ck.keys()))
assert "gate" in ck, "checkpoint tidak memuat gate, pastikan ini hasil Stage 5"

p = pathlib.Path("configs/stage6_localization.yaml")
cfg = yaml.safe_load(p.read_text())
cfg["data"]["rffnet_root"] = RFFNET
cfg["model"]["base_checkpoint"] = "weights_final/fusion_v2_gated.pth"
cfg["run_id"] = "stage6_20260827_localization"
cfg["checkpoint"]["out_dir"] = "runs/stage6_20260827_localization"
cfg["inference_service"]["production_method"] = "segmentation_head"
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
print("\n" + p.read_text())

# %% [markdown]
# ## Sel 3 — Konfirmasi pembukaan split uji
#
# Jalankan sel ini secara sadar. Ia hanya mencatat, tidak mengubah apa pun.

# %%
CATATAN = """
Split uji rffnet_test.csv dibuka untuk keempat kalinya, 27 Agustus 2026, RUN 5.
Pembukaan 1: Stage 6 semifinal, evaluasi lokalisasi.
Pembukaan 2: sapuan tau saat penulisan paper, model TIDAK berubah.
Pembukaan 3: RUN 2C, 26 Agustus 2026, model BERUBAH (Stage 1+2 dilatih ulang,
kriteria seleksi P9 diganti).
Pembukaan 4: run ini, atas fusion_v2_gated.pth hasil RUN 4 (Stage 5 di atas
checkpoint RUN 2C). Model berubah lagi sejak pembukaan 3, jadi ini evaluasi
atas model BARU, bukan pengulangan atas model yang sama.
Tidak ada keputusan penyetelan yang diambil berdasarkan angka split uji pada
pembukaan mana pun.
""".strip()
print(CATATAN)
pathlib.Path("reports").mkdir(exist_ok=True)
pathlib.Path("reports/CATATAN_SPLIT_UJI.txt").write_text(CATATAN, encoding="utf-8")
print("\ntercatat di reports/CATATAN_SPLIT_UJI.txt")

# %% [markdown]
# ## Sel 4 — Jalankan Stage 6

# %%
!python src/train.py --config configs/stage6_localization.yaml

# %% [markdown]
# ## Sel 5 — SIMPAN SEKARANG
#
# Sengaja mendahului seluruh pemeriksaan. Dengan Save & Run All, satu galat di
# sel pelaporan menggagalkan seluruh versi dan zip tidak pernah terbentuk. Itu
# yang menghanguskan tiga run Stage 5 yang sudah berhasil di RUN 4.
#
# `runs/` TIDAK disalin: isinya checkpoint per-epoch, dan itulah yang membuat
# zip RUN 2B membengkak jadi 2274,9 MB.

# %%
import shutil, os, pathlib

OUT = pathlib.Path("/kaggle/working/keluaran")
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
shutil.copytree("weights_final", OUT / "weights_final")
shutil.copytree("reports", OUT / "reports")

(OUT / "runs_ringkasan").mkdir(exist_ok=True)
for q in pathlib.Path("runs").rglob("*"):
    if q.is_file() and q.suffix in (".json", ".yaml", ".txt", ".csv"):
        tujuan = OUT / "runs_ringkasan" / q.relative_to("runs")
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(q, tujuan)

def buat_zip():
    shutil.make_archive("/kaggle/working/stage6_hasil", "zip", OUT)
    return os.path.getsize("/kaggle/working/stage6_hasil.zip") / 1024 ** 2

print(f"stage6_hasil.zip : {buat_zip():.1f} MB")
for q in sorted((OUT / "weights_final").glob("*.pth")):
    print("  ", q.name, round(q.stat().st_size / 1024 ** 2, 1), "MB")
print("\nHASIL SUDAH AMAN. Sel berikutnya hanya pelaporan.")

# %% [markdown]
# ## Sel 6 — Periksa hasil
#
# Acuan lama: mIoU uji 0,5328 dan pointing game 0,6133 yaitu 92 dari 150.
# Kedua jalur **tidak diukur pada metrik yang sama**, jadi ini bukan
# perbandingan langsung dan tidak boleh ditulis sebagai salah satu lebih baik.

# %%
try:
    import csv, pathlib, torch

    q = pathlib.Path("reports/ablation3_localization_weak_vs_full.csv")
    if q.exists():
        for r in csv.DictReader(open(q, encoding="utf-8")):
            print({k: v for k, v in r.items() if v})
    else:
        print("ablation3 csv tidak ada")

    sq = pathlib.Path("weights_final/segmentation_head_v1.pth")
    if sq.exists():
        seg = torch.load(sq, map_location="cpu", weights_only=False)
        miou = seg.get("val_miou")
        miou_s = f"{miou:.4f}" if isinstance(miou, (int, float)) else str(miou)
        print(f"\nhead segmentasi: epoch {seg.get('epoch')}, val_mIoU {miou_s}")
        print("acuan lama    : epoch 23, val_mIoU 0.5595, mIoU uji 0.5328")

    print("\npenyebut pointing game acuan lama: 150 dari 200 sampel uji")
    print("\nCATATAN untuk slide: Stage 6 dijalankan SATU kali, bukan tiga benih.")
    print("Berbeda dari Ablation #1 dan #2, di sini tidak ada simpangan yang")
    print("dapat dilaporkan. Tulis apa adanya, jangan bandingkan kedua jalur")
    print("seolah selisihnya bermakna.")
except Exception as e:
    print("sel pelaporan gagal, diabaikan. Zip sudah aman sejak Sel 5:", e)
