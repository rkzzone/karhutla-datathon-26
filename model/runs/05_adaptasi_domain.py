# %% [markdown]
# # RUN 6 — Stage 7, kesenjangan domain dengan benih dikunci
#
# Versi lama **tidak mengunci benih** pada loop pelatihan LoRA, sehingga kurva
# N=0/10/25/50/100 keluar 92/92/95/100/86 persen: tidak monoton, dan berubah
# antar run. Run ini menguncinya dan mengulang tiga kali agar hasilnya punya
# simpangan yang dapat dilaporkan.
#
# ## Input
#
# | Dataset Kaggle | Isi |
# |---|---|
# | `kode-orang-a-patched` | kode tertambal |
# | `ckpt-fusion-gated` | hasil RUN 4 |
# | `flame-3` | FLAME 3 CV subset |
#
# ## Keluaran
# `domain_gap_lora_curve_seed{42,43,44}.csv` dan rerata beserta simpangannya
#
# **Perkiraan 1 jam untuk tiga benih.**

# %% [markdown]
# ## Sel 1 — Path

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

KODE = str(Path(_cari('src/train.py', nama='folder kode')).parent.parent)
GATED = "/kaggle/input/ckpt-fusion-gated"

print("kandidat folder FLAME 3:")
for p in Path("/kaggle/input").rglob("*"):
    if p.is_dir() and p.name.lower() in ("fire", "no fire", "rgb", "thermal"):
        print("   ", p.parent)
        break

FLAME3 = "/kaggle/input/flame-3"          # SESUAIKAN dengan hasil di atas
CKPT = next(Path(GATED).rglob("fusion_v2_gated.pth"))
print("\nFLAME3 =", FLAME3)
print("CKPT   =", CKPT)

# %% [markdown]
# ## Sel 2 — Salin dan sesuaikan config
#
# Perhatikan `run_which`: versi lama masih tertulis `thermal_regime` padahal
# yang dijalankan `domain_gap_lora`. Diperbaiki di sini.

# %%
import shutil, pathlib, yaml, os, torch

REPO = pathlib.Path("/kaggle/working/repo")
if REPO.exists():
    shutil.rmtree(REPO)
shutil.copytree(KODE, REPO)
os.chdir(REPO)

pathlib.Path("weights_final").mkdir(exist_ok=True)
shutil.copy(CKPT, "weights_final/fusion_v2_gated.pth")

p = pathlib.Path("configs/stage7_domain_adapt.yaml")
cfg = yaml.safe_load(p.read_text())
cfg["run_which"] = "domain_gap_lora"          # perbaikan, versi lama keliru
cfg["data"]["flame3_root"] = FLAME3
cfg["domain_gap_lora"]["base_checkpoint"] = "weights_final/fusion_v2_gated.pth"
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
print(p.read_text())

# %% [markdown]
# ## Sel 3 — Patch penguncian benih
#
# Tanpa ini, hubungan antara jumlah sampel adaptasi dan performa tidak dapat
# diklaim sama sekali.

# %%
f = pathlib.Path("src/train.py")
s = f.read_text(encoding="utf-8")

lama = "def run_stage7(config: dict, device: torch.device):"
baru = '''def run_stage7(config: dict, device: torch.device):
    # [PATCH RUN6] Kunci SELURUH sumber keacakan. Versi lama hanya membuat
    # pemisahan data deterministik, sedangkan inisialisasi bobot LoRA dan urutan
    # batch tidak, sehingga kurvanya berubah antar run.
    import random as _rnd
    import numpy as _np
    _seed = int(config.get("seed", 42))
    torch.manual_seed(_seed)
    torch.cuda.manual_seed_all(_seed)
    _np.random.seed(_seed)
    _rnd.seed(_seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    print(f"[Stage7][PATCH RUN6] seluruh benih dikunci ke {_seed}")'''

assert s.count(lama) == 1
f.write_text(s.replace(lama, baru), encoding="utf-8")

import py_compile
py_compile.compile("src/train.py", doraise=True)
print("patch benih diterapkan, sintaks OK")

# %% [markdown]
# ## Sel 4 — Jalankan tiga benih

# %%
import yaml, pathlib, shutil

for SEED in [42, 43, 44]:
    print("\n" + "=" * 62)
    print(f"  benih {SEED}")
    print("=" * 62)
    p = pathlib.Path("configs/stage7_domain_adapt.yaml")
    cfg = yaml.safe_load(p.read_text())
    cfg["seed"] = SEED
    cfg["run_id"] = f"stage7_20260824_lora_seed{SEED}"
    cfg["domain_gap_lora"]["output_csv"] = f"reports/domain_gap_lora_curve_seed{SEED}.csv"
    p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    !python src/train.py --config configs/stage7_domain_adapt.yaml

# %% [markdown]
# ## Sel 5 — Rerata dan simpangan tiga benih
#
# **Inilah keluaran yang dilaporkan**, bukan angka satu benih. Bila simpangannya
# besar, itu jawabannya: adaptasi few-shot pada N kecil memang tidak stabil, dan
# sekarang ada angkanya, bukan sekadar catatan.

# %%
import csv, pathlib, statistics

kurva = {}
for SEED in [42, 43, 44]:
    f = pathlib.Path(f"reports/domain_gap_lora_curve_seed{SEED}.csv")
    if not f.exists():
        print(f"benih {SEED}: berkas tidak ada")
        continue
    for r in csv.DictReader(open(f, encoding="utf-8")):
        kurva.setdefault(int(r["n_adapt"]), []).append(float(r["accuracy"]))

print(f"{'N_adapt':>8s} {'rerata':>8s} {'simpangan':>10s} {'min':>7s} {'maks':>7s}  nilai")
print("-" * 66)
baris_akhir = []
for n in sorted(kurva):
    v = kurva[n]
    sd = statistics.stdev(v) if len(v) > 1 else 0.0
    print(f"{n:8d} {statistics.mean(v) * 100:7.2f}% {sd * 100:9.2f}p "
          f"{min(v) * 100:6.2f}% {max(v) * 100:6.2f}%  {[round(x * 100, 1) for x in v]}")
    baris_akhir.append({"n_adapt": n, "accuracy_mean": statistics.mean(v),
                        "accuracy_std": sd, "n_seed": len(v)})

with open("reports/domain_gap_lora_curve_RERATA.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["n_adapt", "accuracy_mean", "accuracy_std", "n_seed"])
    w.writeheader(); w.writerows(baris_akhir)
print("\n-> reports/domain_gap_lora_curve_RERATA.csv")

print("\nAcuan satu benih versi lama: 92 / 92 / 95 / 100 / 86 persen, tidak monoton.")
print("Yang boleh diklaim hanyalah generalisasi zero-shot pada N=0.")
print("Ingat: FLAME 2 dan FLAME 3 sama-sama di Amerika Serikat dan beriklim")
print("sedang, jadi angka ini BUKAN bukti transfer ke gambut tropis.")

# %% [markdown]
# ## Sel 6 — Simpan

# %%
import shutil, os

shutil.make_archive("/kaggle/working/stage7_hasil", "zip", "reports")
print("stage7_hasil.zip :",
      round(os.path.getsize("/kaggle/working/stage7_hasil.zip") / 1024 ** 2, 1), "MB")
