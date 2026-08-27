# %% [markdown]
# # RUN 2C — Stage 2 dengan kriteria seleksi diperbaiki, plus kurva degradasi
#
# **Menggantikan RUN 2B, dan sekaligus menyerap RUN 3.** Melatih dan mengevaluasi
# dalam satu sesi menghapus satu siklus unggah-unduh berukuran sekitar 1 GB.
#
# ## Kenapa RUN 2B tidak dapat dipakai
#
# RUN 2B berhasil mengunci benih, dan justru karena itu ia memperlihatkan masalah
# yang jauh lebih besar. Dari 12 run:
#
# | mode | rentang | simpangan |
# |---|---|---|
# | fusi | 98,33 sampai 100,00 | 0,65 poin |
# | RGB saja | 75,00 sampai 100,00 | 6,86 poin |
# | termal saja | 48,33 sampai 97,50 | **19,23 poin** |
#
# Akurasi fusi di rffnet_val **jenuh**. Banyak epoch berimpit di 1,0000, dan
# checkpoint dipilih berdasarkan angka itu. Ketika banyak epoch seri, epoch mana
# yang tersimpan praktis acak terhadap hal yang tidak diukur, yaitu jalur
# unimodal. Padahal jalur unimodal itulah tumpuan seluruh klaim ketahanan.
#
# Dua akibat langsung, keduanya membatalkan kesimpulan sebelumnya:
#
# 1. **Sapuan p tidak dapat ditafsirkan.** Selisih antar-p jauh lebih kecil
#    daripada simpangan antar-benih di kolom yang menjadi tumpuan klaim.
# 2. **Klaim A/B encoder termal gugur.** Angka satu benih di RUN 2 adalah
#    +44,60 poin untuk encoder baru. Dengan tiga benih arahnya **terbalik**,
#    yaitu -18,61 poin, dengan simpangan gabungan 23,61 poin. Tidak ada beda
#    yang dapat diklaim ke arah mana pun.
#
# ## Yang diubah
#
# **P9** mengganti kriteria seleksi checkpoint menjadi rerata akurasi tiga mode
# ketersediaan modalitas. Ini bukan sekadar lebih stabil, melainkan kriteria yang
# memang sesuai dengan tujuan: melatih dengan modality dropout lalu memilih model
# berdasarkan akurasi kondisi bersih adalah memilih dengan ukuran yang bukan
# tujuannya.
#
# **P10** menambah `--tag`, supaya run encoder LAMA tidak lagi menimpa run
# encoder BARU. Di RUN 2B keduanya menulis ke nama yang sama, penggantian nama
# baru terjadi sesudahnya, sehingga seluruh hasil p=0,2 encoder BARU hilang dari
# disk dan hanya tersisa di log.
#
# ## Disiplin pelaporan
#
# Seleksi memakai **val**, pelaporan memakai **test**. Angka val di Ablation #1
# sekarang adalah angka yang ikut dioptimasi oleh kriteria seleksi, jadi ia
# **tidak boleh** menjadi angka utama di slide. Sel 7 mengevaluasi test.
#
# ## Input
#
# | Dataset Kaggle | Isi |
# |---|---|
# | `kode-orang-a-patched-v5` | kode dengan P9 dan P10 |
# | `ckpt-thermal-p5` | encoder BARU, hasil RUN 1 |
# | `ckpt-thermal-lama` | encoder LAMA, untuk A/B |
# | `abangbuan/flame2` | data RFFNet |
#
# **Lepas v3 dan v4 dari Input notebook.** Penjaga di Sel 1 akan menolak bila
# yang terbaca versi lama.
#
# Perkiraan: 12 run latih sekitar 80 menit, evaluasi sekitar 15 menit.

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

_tr = pathlib.Path('src/train.py').read_text(encoding='utf-8')
_ds = pathlib.Path('src/data/dataset_flame2.py').read_text(encoding='utf-8')
for penanda, berkas, isi in [('def split_by_block', 'dataset_flame2.py', _ds),
                             ('[PATCH P7]', 'train.py', _tr),
                             ('[PATCH P8]', 'train.py', _tr),
                             ('[PATCH P9]', 'train.py', _tr),
                             ('[PATCH P10]', 'train.py', _tr)]:
    assert penanda in isi, (
        f"{penanda} tidak ada di {berkas}. Dataset kode terpasang versi lama. "
        "Lepas v3 dan v4 dari Input notebook, sisakan hanya v5.")
print("penjaga kode: P6 sampai P10 terdeteksi")

for nama, jalur, harap in [("BARU", CKPT_BARU, 0.9758), ("LAMA", CKPT_LAMA, 0.5148)]:
    ck = torch.load(jalur, map_location="cpu", weights_only=False)
    va = float(ck.get("val_acc"))
    print(f"  encoder {nama}: epoch {ck.get('epoch')}, val_acc {va:.4f}")
    assert abs(va - harap) < 0.01, f"encoder {nama} bukan yang diharapkan (harap ~{harap})"

p = pathlib.Path("configs/stage2_finetune_fusion.yaml")
cfg = yaml.safe_load(p.read_text())
cfg["data"]["rffnet_root"] = RFFNET
cfg["run_id"] = "stage2_20260826_seleksi"
cfg["checkpoint"]["out_dir"] = "runs/stage2_20260826_seleksi"
cfg["training"]["selection_criterion"] = "rerata_tiga_mode"     # [P9] eksplisit di config
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
print("\nkriteria seleksi:", cfg["training"]["selection_criterion"])
print("GPU:", torch.cuda.device_count())

# %% [markdown]
# ## Sel 2 — Sembilan run sapuan p, encoder BARU
#
# Baris log kini memuat `rgb=`, `termal=`, dan `SKOR=` per epoch, jadi kejenuhan
# kriteria lama dapat dilihat langsung dari log.

# %%
import shutil, pathlib, time

pathlib.Path("weights_final").mkdir(exist_ok=True)
shutil.copy(CKPT_BARU, "weights_final/thermal_encoder_pretrained.pth")
print("encoder BARU terpasang\n")
t_mulai = time.time()

for P in ["0.1", "0.2", "0.3"]:
    for S in [42, 43, 44]:
        print("=" * 62)
        print(f"  encoder BARU - p={P} - benih={S}")
        print("=" * 62)
        cmd = (f"python src/train.py --config configs/stage2_finetune_fusion.yaml"
               f" --p {P} --seed {S}")
        !{cmd}

print(f"\nsembilan run selesai dalam {(time.time()-t_mulai)/60:.1f} menit")

# %% [markdown]
# ## Sel 3 — Tiga run A/B, encoder LAMA
#
# `--tag ENCLAMA` menangani penamaan. Tidak ada lagi penggantian nama sesudah
# run, karena itulah yang merusak RUN 2B.

# %%
shutil.copy(CKPT_LAMA, "weights_final/thermal_encoder_pretrained.pth")
print("encoder LAMA terpasang\n")

for S in [42, 43, 44]:
    print("=" * 62)
    print(f"  encoder LAMA - p=0.2 - benih={S}")
    print("=" * 62)
    cmd = (f"python src/train.py --config configs/stage2_finetune_fusion.yaml"
           f" --p 0.2 --seed {S} --tag ENCLAMA")
    !{cmd}

shutil.copy(CKPT_BARU, "weights_final/thermal_encoder_pretrained.pth")
print("\nencoder BARU dikembalikan sebagai default")

ck = sorted(pathlib.Path("weights_final").glob("fusion_v1_p*.pth"))
print(f"\ncheckpoint terbentuk: {len(ck)}  (harus 12)")
for c in ck:
    print("   ", c.name)
assert len(ck) == 12, "jumlah checkpoint tidak 12, ada yang tertimpa"

# %% [markdown]
# ## Sel 4 — Bukti bahwa P9 bekerja
#
# Bila kriteria lama memang jenuh, epoch terpilih sekarang seharusnya berbeda,
# dan akurasi termal pada epoch terpilih seharusnya jauh lebih rapat antar-benih.

# %%
import torch, statistics as st

print(f"{'checkpoint':>30s} {'epoch':>6s} {'fusi':>7s} {'rgb':>7s} {'termal':>7s} {'skor':>7s}")
print("-" * 70)
kump = {}
for c in ck:
    d = torch.load(c, map_location="cpu", weights_only=False)
    pm = d.get("val_acc_per_mode", {})
    kunci = c.stem.replace("fusion_v1_", "")
    grup = "ENCLAMA" if "ENCLAMA" in kunci else kunci.split("_")[0]
    kump.setdefault(grup, []).append(pm.get("termal", float("nan")))
    print(f"{c.name:>30s} {d.get('epoch'):6d} {pm.get('fusi', 0):7.4f} "
          f"{pm.get('rgb', 0):7.4f} {pm.get('termal', 0):7.4f} "
          f"{d.get('val_acc_rerata', 0):7.4f}")

print(f"\n{'kelompok':>10s} {'termal rerata':>14s} {'simpangan':>11s}   pembanding")
print("-" * 64)
ACUAN = {"p01": 4.73, "p02": 24.22, "p03": 17.35, "ENCLAMA": 22.98}
for g in ["p01", "p02", "p03", "ENCLAMA"]:
    v = [x * 100 for x in kump.get(g, [])]
    if len(v) < 2:
        continue
    print(f"{g:>10s} {st.mean(v):13.2f}% {st.stdev(v):10.2f}p   "
          f"RUN 2B simpangan {ACUAN[g]:.2f}p")
print("\nBila simpangan turun tajam, kejenuhan kriteria lama terkonfirmasi")
print("sebagai penyebab, bukan ketidakstabilan pelatihan itu sendiri.")

# %% [markdown]
# ## Sel 5 — Ablation #3, sapuan p
#
# Ini angka **val**, dan val ikut dioptimasi oleh kriteria seleksi. Pakai untuk
# memilih p, jangan dipakai sebagai angka utama di slide.

# %%
import csv, pathlib, statistics as st

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

def baris(nama, k):
    sel = []
    for m in ["fusi_penuh", "rgb_saja", "termal_saja"]:
        v = k.get(m, [])
        sd = st.stdev(v) if len(v) > 1 else 0.0
        sel.append(f"{st.mean(v)*100:6.2f} +/- {sd*100:5.2f}")
    print(f"{nama:>10s} | {sel[0]:>15s} | {sel[1]:>15s} | {sel[2]:>15s}")

print("ABLATION #3 pada val - sensitivitas p, encoder BARU, rerata 3 benih")
print(f"{'p':>10s} | {'fusi':>15s} | {'RGB saja':>15s} | {'termal saja':>15s}")
print("-" * 68)
for P, tag in [("0.1", "p01"), ("0.2", "p02"), ("0.3", "p03")]:
    k = ringkas([f"{tag}_s{s}" for s in (42, 43, 44)])
    if k:
        baris(P, k)
    else:
        print(f"{P:>10s} | berkas tidak ada")

print("\nA/B ENCODER TERMAL pada val, p = 0,2, rerata 3 benih")
print(f"{'encoder':>10s} | {'fusi':>15s} | {'RGB saja':>15s} | {'termal saja':>15s}")
print("-" * 68)
for nama, tags in [("LAMA", [f"p02_s{s}_ENCLAMA" for s in (42, 43, 44)]),
                   ("BARU", [f"p02_s{s}" for s in (42, 43, 44)])]:
    k = ringkas(tags)
    if k:
        baris(nama, k)
    else:
        print(f"{nama:>10s} | berkas tidak ada")

# %% [markdown]
# ## Sel 6 — Catatan pembukaan split uji
#
# Jalankan sadar-sadar. Sel ini hanya mencatat, tidak mengubah apa pun.

# %%
import pathlib

CATATAN = """
Pembukaan split uji rffnet_test.csv, 26 Agustus 2026, RUN 2C.
Pembukaan 1: Stage 6 semifinal, evaluasi lokalisasi.
Pembukaan 2: sapuan tau saat penulisan paper, model TIDAK berubah.
Pembukaan 3: run ini. Model berubah, karena Stage 1 dilatih ulang dengan batas
video terkoreksi dan kriteria seleksi Stage 2 diganti. Ini evaluasi atas model
baru, bukan pengulangan atas model yang sama.
Tidak ada keputusan penyetelan yang diambil berdasarkan angka split uji.
Pemilihan p dilakukan di split validasi, lihat Sel 5.
""".strip()
pathlib.Path("reports").mkdir(exist_ok=True)
pathlib.Path("reports/CATATAN_SPLIT_UJI.txt").write_text(CATATAN, encoding="utf-8")
print(CATATAN)

# %% [markdown]
# ## Sel 7 — Kurva degradasi, menyerap RUN 3
#
# Dua belas checkpoint, tiga partisi, enam level tau, di sesi yang sama supaya
# checkpoint sebesar 1,4 GB tidak perlu keluar-masuk Kaggle.

# %%
TAU = "0.0 0.2 0.4 0.6 0.8 1.0"
t_mulai = time.time()

for c in ck:
    TAG = c.stem.replace("fusion_v1_", "")
    print("\n" + "=" * 62)
    print(f"  evaluasi {TAG}")
    print("=" * 62)
    cmd = (f"python src/eval_paper_metrics.py"
           f" --checkpoint weights_final/{c.name}"
           f" --rffnet-root {RFFNET}"
           f" --splits train val test"
           f" --tau {TAU}"
           f" --out-dir reports/sweep_{TAG}")
    !{cmd}

print(f"\nevaluasi selesai dalam {(time.time()-t_mulai)/60:.1f} menit")

# %% [markdown]
# ## Sel 8 — Kurva degradasi pada TEST, dengan simpangan antar-benih
#
# **Inilah angka yang masuk slide.** Test, tiga benih, dengan simpangan.

# %%
import csv, pathlib, statistics as st

def kurva(tag, split):
    f = pathlib.Path(f"reports/sweep_{tag}/degradation_curve_{split}.csv")
    return list(csv.DictReader(open(f, encoding="utf-8"))) if f.exists() else None

def kumpul(tags, split, kolom):
    per_tau = {}
    for t in tags:
        rows = kurva(t, split)
        if not rows:
            continue
        for r in rows:
            per_tau.setdefault(float(r["tau"]), []).append(float(r[kolom]) * 100)
    return per_tau

KELOMPOK = [("p=0.1", [f"p01_s{s}" for s in (42, 43, 44)]),
            ("p=0.2", [f"p02_s{s}" for s in (42, 43, 44)]),
            ("p=0.3", [f"p03_s{s}" for s in (42, 43, 44)]),
            ("LAMA", [f"p02_s{s}_ENCLAMA" for s in (42, 43, 44)])]

for split in ["val", "test"]:
    print(f"\n=== akurasi fusi saat termal didegradasi, partisi {split} ===")
    judul = " ".join(f"{('t=' + str(t)):>13s}" for t in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    print(f"{'kelompok':>9s} | {judul}")
    print("-" * 95)
    for nama, tags in KELOMPOK:
        pt = kumpul(tags, split, "acc_fusion")
        if not pt:
            print(f"{nama:>9s} | berkas tidak ada")
            continue
        sel = []
        for t in sorted(pt):
            v = pt[t]
            sd = st.stdev(v) if len(v) > 1 else 0.0
            sel.append(f"{st.mean(v):6.2f}+/-{sd:4.1f}")
        print(f"{nama:>9s} | " + " ".join(f"{x:>13s}" for x in sel))

    print(f"\n{'kelompok':>9s} | {'turun t0 ke t1':>17s} | bentuk")
    print("-" * 56)
    for nama, tags in KELOMPOK:
        pt = kumpul(tags, split, "acc_fusion")
        if not pt:
            continue
        ts = sorted(pt)
        turun = [a - b for a, b in zip(pt[ts[0]], pt[ts[-1]])]
        sd = st.stdev(turun) if len(turun) > 1 else 0.0
        m = st.mean(turun)
        bentuk = "MEMBALIK (naik)" if m < -0.5 else ("datar" if abs(m) <= 0.5 else "menurun")
        print(f"{nama:>9s} | {m:10.2f} +/- {sd:4.2f} | {bentuk}")

print("\nBACAAN. Bila LAMA membalik dan BARU menurun, pembalikan pada paper")
print("semifinal terjelaskan oleh encoder termal, bukan oleh arsitektur fusi.")
print("Bila keduanya datar dalam batas simpangan, yang jujur dilaporkan adalah")
print("bahwa tolok ukur ini tidak punya daya pembeda, dan itu tetap temuan sah")
print("karena ia menjelaskan kenapa hasil semifinal tidak stabil.")

# %% [markdown]
# ## Sel 9 — Simpan
#
# RUN 2B menghasilkan zip 2274,9 MB karena ikut menyalin `runs/`, yang berisi
# `checkpoint_best` dan `checkpoint_last` untuk tiap dari 12 run. Di sini `runs/`
# tidak disalin utuh, dan hanya checkpoint yang dibutuhkan RUN 4 dan RUN 5 ikut.

# %%
import shutil, os, pathlib

# Ganti sesuai tabel Sel 5. Bila ketiganya berimpit dalam batas simpangan,
# biarkan p02 dan katakan di slide bahwa p tidak dipilih berdasarkan hasil
# melainkan dipertahankan karena tidak ada pembeda yang melewati derau.
P_TERPILIH = "p02"

OUT = pathlib.Path("/kaggle/working/keluaran")
if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "weights_final").mkdir(parents=True)
shutil.copytree("reports", OUT / "reports")

(OUT / "runs_ringkasan").mkdir()
for f in pathlib.Path("runs").rglob("*"):
    if f.is_file() and f.suffix in (".json", ".yaml", ".txt", ".csv"):
        tujuan = OUT / "runs_ringkasan" / f.relative_to("runs")
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f, tujuan)

for s in (42, 43, 44):
    src = pathlib.Path("weights_final") / f"fusion_v1_{P_TERPILIH}_s{s}.pth"
    if src.exists():
        shutil.copy(src, OUT / "weights_final" / src.name)

shutil.make_archive("/kaggle/working/stage2c_hasil", "zip", OUT)
uk = os.path.getsize("/kaggle/working/stage2c_hasil.zip") / 1024 ** 2
print(f"stage2c_hasil.zip : {uk:.1f} MB   (RUN 2B: 2274,9 MB)")
for p in sorted((OUT / "weights_final").glob("*.pth")):
    print("  ", p.name, round(p.stat().st_size / 1024 ** 2, 1), "MB")
print(f"  CSV ablation : {len(list((OUT / 'reports').glob('ablation1_*.csv')))}  (harus 12)")
print(f"  folder sweep : {len(list((OUT / 'reports').glob('sweep_*')))}  (harus 12)")
n_ps = len(list((OUT / "reports").rglob("per_sample_predictions_*.csv")))
print(f"  per-sampel   : {n_ps}  (harus 216 = 12 checkpoint x 3 split x 6 tau)")
assert uk < 700, "zip masih terlalu besar, periksa apakah runs/ ikut tersalin"
