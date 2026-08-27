# %% [markdown]
# # RUN 2B — Sapuan p dan A/B encoder, dengan benih dikunci
#
# **Kenapa RUN 2 perlu diulang.** RUN 2 mengungkap dua hal yang membuat hasilnya
# belum bisa diklaim:
#
# 1. **Stage 2 tidak pernah diberi benih.** Tidak ada satu pun `torch.manual_seed`
#    di seluruh `train.py`, padahal `seed: 42` tercantum di setiap config. Dua run
#    dengan konfigurasi identik menghasilkan RGB 0,9833 dan 0,9292: selisih 5,4
#    poin murni dari keacakan. Sapuan p yang selisihnya 1-2 sampel jelas tidak
#    dapat ditafsirkan di atas derau sebesar itu.
# 2. **`fusion_v1_p02.pth` tertimpa** oleh run A/B, sehingga tabel Sel 5 dan
#    berkas di disk tidak lagi cocok.
#
# Patch **P8** pada `kode-orang-a-patched-v4` mengunci seluruh benih dan menambah
# `--seed` yang memberi sufiks pada keluaran, sehingga tidak ada lagi penimpaan.
#
# ## Input
#
# | Dataset Kaggle | Isi |
# |---|---|
# | `kode-orang-a-patched-v4` | kode dengan P8 |
# | `ckpt-thermal-p5` | encoder BARU, hasil RUN 1 |
# | `ckpt-thermal-lama` | encoder LAMA, untuk A/B |
# | `abangbuan/flame2` | data RFFNet |
#
# ## Rencana run
#
# | Kelompok | Konfigurasi | Jumlah |
# |---|---|---|
# | Sapuan p, encoder BARU | p ∈ {0,1 · 0,2 · 0,3} × benih {42 · 43 · 44} | 9 |
# | A/B, encoder LAMA | p = 0,2 × benih {42 · 43 · 44} | 3 |
#
# Satu run sekitar 4 menit, jadi total **sekitar 50 menit**.

# %% [markdown]
# ## Sel 1 — Path otomatis dan penjaga versi

# %%
from pathlib import Path

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

RFFNET = None
for gt in Path("/kaggle/input").rglob("img_gt_*.png"):
    RFFNET = str(gt.parent.parent)
    break
assert RFFNET, "data RFFNet tidak ditemukan"

KODE = str(Path(_cari('src/train.py', nama='folder kode')).parent.parent)
CKPT_BARU = _cari('thermal_encoder_pretrained.pth', nama='encoder termal BARU')
CKPT_LAMA = _cari('thermal_encoder_LAMA_legacy.pth', nama='encoder termal LAMA')

print("RFFNET    =", RFFNET)
print("KODE      =", KODE)
print("CKPT_BARU =", CKPT_BARU)
print("CKPT_LAMA =", CKPT_LAMA)

# %%
import shutil, pathlib, yaml, os, torch

REPO = pathlib.Path("/kaggle/working/repo")
if REPO.exists():
    shutil.rmtree(REPO)
shutil.copytree(KODE, REPO)
os.chdir(REPO)

# PENJAGA versi kode: P6, P7, P8 harus ada semua
_tr = pathlib.Path('src/train.py').read_text(encoding='utf-8')
_ds = pathlib.Path('src/data/dataset_flame2.py').read_text(encoding='utf-8')
for penanda, berkas, isi in [('def split_by_block', 'dataset_flame2.py', _ds),
                             ('[PATCH P7]', 'train.py', _tr),
                             ('[PATCH P8]', 'train.py', _tr)]:
    assert penanda in isi, (
        f"{penanda} tidak ada di {berkas}. Dataset kode yang terpasang versi lama. "
        "Lepas versi lama dari Input notebook, sisakan hanya v4.")
print("penjaga kode: P6, P7, P8 terdeteksi")

for nama, jalur, harap in [("BARU", CKPT_BARU, 0.9758), ("LAMA", CKPT_LAMA, 0.5148)]:
    ck = torch.load(jalur, map_location="cpu", weights_only=False)
    va = float(ck.get("val_acc"))
    print(f"  encoder {nama}: epoch {ck.get('epoch')}, val_acc {va:.4f}")
    assert abs(va - harap) < 0.01, f"encoder {nama} bukan yang diharapkan (harap ~{harap})"

p = pathlib.Path("configs/stage2_finetune_fusion.yaml")
cfg = yaml.safe_load(p.read_text())
cfg["data"]["rffnet_root"] = RFFNET
cfg["run_id"] = "stage2_20260824_sweep"
cfg["checkpoint"]["out_dir"] = "runs/stage2_20260824_sweep"
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
print("\nGPU:", torch.cuda.device_count())

# %% [markdown]
# ## Sel 2 — Sembilan run sapuan p, encoder BARU
#
# Keluaran diberi sufiks `_p0X_sYY`, jadi tidak ada yang saling menimpa.

# %%
import shutil, pathlib

pathlib.Path("weights_final").mkdir(exist_ok=True)
shutil.copy(CKPT_BARU, "weights_final/thermal_encoder_pretrained.pth")
print("encoder BARU terpasang\n")

for P in ["0.1", "0.2", "0.3"]:
    for S in [42, 43, 44]:
        print("=" * 62)
        print(f"  encoder BARU · p={P} · benih={S}")
        print("=" * 62)
        cmd = (f"python src/train.py --config configs/stage2_finetune_fusion.yaml"
               f" --p {P} --seed {S}")
        !{cmd}

# %% [markdown]
# ## Sel 3 — Tiga run A/B, encoder LAMA pada p = 0,2

# %%
shutil.copy(CKPT_LAMA, "weights_final/thermal_encoder_pretrained.pth")
print("encoder LAMA terpasang\n")

for S in [42, 43, 44]:
    print("=" * 62)
    print(f"  encoder LAMA · p=0.2 · benih={S}")
    print("=" * 62)
    cmd = (f"python src/train.py --config configs/stage2_finetune_fusion.yaml"
           f" --p 0.2 --seed {S}")
    !{cmd}
    # beri nama berbeda SEBELUM run berikutnya, supaya tidak tertimpa
    for asal, tujuan in [(f"weights_final/fusion_v1_p02_s{S}.pth",
                          f"weights_final/fusion_v1_p02_s{S}_ENCLAMA.pth"),
                         (f"reports/ablation1_unimodal_vs_fusion_p02_s{S}.csv",
                          f"reports/ablation1_unimodal_vs_fusion_p02_s{S}_ENCLAMA.csv")]:
        if pathlib.Path(asal).exists():
            shutil.move(asal, tujuan)

shutil.copy(CKPT_BARU, "weights_final/thermal_encoder_pretrained.pth")
print("\nencoder BARU dikembalikan sebagai default")

# %% [markdown]
# ## Sel 4 — Ablation #3 dengan rerata dan simpangan
#
# **Inilah yang masuk slide.** Angka satu run tidak dilaporkan lagi.

# %%
import csv, statistics, pathlib

def baca(tag):
    f = pathlib.Path(f"reports/ablation1_unimodal_vs_fusion_{tag}.csv")
    if not f.exists():
        return None
    return {r["mode"]: float(r["accuracy"]) for r in csv.DictReader(open(f, encoding="utf-8"))}

def ringkas(tags):
    kump = {}
    for t in tags:
        b = baca(t)
        if not b:
            continue
        for m, v in b.items():
            kump.setdefault(m, []).append(v)
    return kump

print("ABLATION #3 — sensitivitas p, encoder BARU, rerata 3 benih")
print(f"{'p':>5s} | {'fusi':>16s} | {'RGB saja':>16s} | {'termal saja':>16s}")
print("-" * 64)
hasil_p = {}
for P, tag in [("0.1", "p01"), ("0.2", "p02"), ("0.3", "p03")]:
    k = ringkas([f"{tag}_s{s}" for s in (42, 43, 44)])
    if not k:
        print(f"{P:>5s} | berkas tidak ada")
        continue
    hasil_p[P] = k
    sel = []
    for m in ["fusi_penuh", "rgb_saja", "termal_saja"]:
        v = k.get(m, [])
        sd = statistics.stdev(v) if len(v) > 1 else 0.0
        sel.append(f"{statistics.mean(v)*100:7.2f} ± {sd*100:4.2f}")
    print(f"{P:>5s} | {sel[0]:>16s} | {sel[1]:>16s} | {sel[2]:>16s}")

print("\nCatatan: bila selisih antar-p lebih kecil daripada simpangannya, maka")
print("sensitivitas terhadap p TIDAK dapat disimpulkan dari akurasi bersih.")
print("Pembeda sesungguhnya ada di kurva degradasi, RUN 3.")

# %% [markdown]
# ## Sel 5 — A/B encoder termal, rerata dan simpangan
#
# Ini temuan inti Skenario C. Kolom **termal saja** yang menentukan, karena
# hanya jalur itu yang bergantung langsung pada encoder termal.

# %%
baru = ringkas([f"p02_s{s}" for s in (42, 43, 44)])
lama = ringkas([f"p02_s{s}_ENCLAMA" for s in (42, 43, 44)])

print("A/B ENCODER TERMAL, p = 0,2, rerata 3 benih")
print(f"{'encoder':>22s} | {'fusi':>15s} | {'RGB saja':>15s} | {'termal saja':>15s}")
print("-" * 78)
for nama, k in [("LAMA (val 0,5148)", lama), ("BARU (val 0,9758)", baru)]:
    if not k:
        print(f"{nama:>22s} | berkas tidak ada")
        continue
    sel = []
    for m in ["fusi_penuh", "rgb_saja", "termal_saja"]:
        v = k.get(m, [])
        sd = statistics.stdev(v) if len(v) > 1 else 0.0
        sel.append(f"{statistics.mean(v)*100:6.2f} ± {sd*100:4.2f}")
    print(f"{nama:>22s} | {sel[0]:>15s} | {sel[1]:>15s} | {sel[2]:>15s}")

if baru and lama:
    import statistics as st
    vb, vl = baru["termal_saja"], lama["termal_saja"]
    selisih = (st.mean(vb) - st.mean(vl)) * 100
    gab = ((st.stdev(vb) ** 2 + st.stdev(vl) ** 2) / 2) ** 0.5 * 100 if len(vb) > 1 else 0
    print(f"\nselisih termal-saja : {selisih:+.2f} poin")
    print(f"simpangan gabungan  : {gab:.2f} poin")
    print(f"rasio selisih/derau : {abs(selisih)/gab:.1f}x" if gab > 0 else "")

    MAYORITAS_RFFNET = 176 / 240
    print(f"\nkelas terbanyak val RFFNet: {MAYORITAS_RFFNET*100:.1f}%")
    print(f"termal-saja encoder LAMA  : {st.mean(vl)*100:.2f}%  "
          f"{'DI BAWAH tebakan terbanyak' if st.mean(vl) < MAYORITAS_RFFNET else 'di atas'}")
    print(f"termal-saja encoder BARU  : {st.mean(vb)*100:.2f}%  "
          f"{'di atas tebakan terbanyak' if st.mean(vb) > MAYORITAS_RFFNET else 'DI BAWAH'}")

# %% [markdown]
# ## Sel 6 — Simpan, hanya yang diperlukan
#
# RUN 2 menghasilkan zip 1092 MB karena menyimpan semua checkpoint. Kali ini
# hanya satu checkpoint per p yang disimpan, cukup untuk RUN 3.

# %%
import shutil, os, pathlib

OUT = pathlib.Path("/kaggle/working/keluaran")
if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "weights_final").mkdir(parents=True)
shutil.copytree("reports", OUT / "reports")
if pathlib.Path("runs").exists():
    shutil.copytree("runs", OUT / "runs")

# hanya benih 42 per p, ditambah satu pembanding encoder lama
for nama in ["fusion_v1_p01_s42.pth", "fusion_v1_p02_s42.pth", "fusion_v1_p03_s42.pth",
             "fusion_v1_p02_s42_ENCLAMA.pth"]:
    src = pathlib.Path("weights_final") / nama
    if src.exists():
        shutil.copy(src, OUT / "weights_final" / nama)

shutil.make_archive("/kaggle/working/stage2b_hasil", "zip", OUT)
print("stage2b_hasil.zip :",
      round(os.path.getsize("/kaggle/working/stage2b_hasil.zip") / 1024 ** 2, 1), "MB")
for p in sorted((OUT / "weights_final").glob("*.pth")):
    print("  ", p.name, round(p.stat().st_size / 1024 ** 2, 1), "MB")
print(f"  CSV ablation: {len(list((OUT / 'reports').glob('ablation1_*.csv')))} berkas")
