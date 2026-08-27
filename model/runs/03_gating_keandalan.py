# %% [markdown]
# # RUN 4 — Stage 5, reliability gating, tiga checkpoint dasar
#
# Versi ini dirancang untuk **Save & Run All**, yaitu tombol *Save Version*.
# Dalam mode itu notebook dijalankan ulang dari nol secara batch, dan satu
# `assert` yang gagal di sel mana pun membuat seluruh versi gagal.
#
# Karena itu urutannya: **simpan dulu, periksa kemudian.** Zip hasil dibentuk
# segera sesudah pelatihan, sebelum satu pun pemeriksaan dijalankan, dan seluruh
# sel pelaporan dibungkus `try` sehingga tidak dapat menggagalkan versi.
#
# Sebelumnya tidak begitu, dan akibatnya tiga run Stage 5 yang sudah berhasil
# ikut hilang karena sel pemeriksaan di ujung meledak.
#
# ## Input yang dipasang, persis tiga
#
# | Dataset Kaggle | Isi | Penanda |
# |---|---|---|
# | `kode-orang-a-patched-v5` | kode dengan P9 dan P10 | `src/train.py` |
# | `ckpt-fusion-sweep-2c` | zip RUN 2C | `fusion_v1_p02_s42.pth` |
# | `abangbuan/flame2` | anotasi RFFNet | `img_gt_*.png` |
#
# **Lepas semua dataset lain**, khususnya `kode-orang-a-patched-v3` dan `v4`,
# serta `ckpt-fusion-sweep` lama yang berisi zip RUN 2B.
#
# Accelerator **GPU T4 x2**, Internet **ON**.
#
# ## Waktu
#
# Terukur **12,6 menit** untuk tiga run. Perkiraan lama saya 45 sampai 90 menit
# per run keliru jauh: model dasar dibekukan, hanya gate head yang dilatih.
#
# ## Keluaran
#
# `stage5_hasil.zip`, berisi 3 `fusion_v2_gated_s*.pth`, 3
# `ablation2_gating_s*.csv`, dan 12 `per_sample_ablation2_gating_s*_tau*.csv`.

# %% [markdown]
# ## Sel 1 — Temukan input, tolak yang keliru

# %%
from pathlib import Path
import torch as _t

# Ablation #3 RUN 2C: rentang rerata antar-p 1,67 poin melawan simpangan khas
# 2,05 poin, rasio 0,81. Ketiganya tidak dapat dibedakan, jadi p02 dipertahankan
# sesuai konfigurasi asli. Tulis di slide bahwa p TIDAK dipilih berdasarkan
# hasil, melainkan dipertahankan karena tidak ada pembeda yang melewati derau.
P_TERPILIH = "p02"

RFFNET = None
for gt in Path("/kaggle/input").rglob("img_gt_*.png"):
    RFFNET = str(gt.parent.parent)
    break
assert RFFNET, "data RFFNet tidak ditemukan. Pasang dataset abangbuan/flame2."

_kode = sorted(Path("/kaggle/input").rglob("src/train.py"), reverse=True)
assert _kode, "folder kode tidak ditemukan. Pasang kode-orang-a-patched-v5."
if len(_kode) > 1:
    print(f"PERINGATAN: {len(_kode)} folder kode terpasang, dipakai yang pertama.")
    for k in _kode:
        print("   ", k)
    print("Sebaiknya lepas versi lama supaya tidak tertukar.\n")
KODE = str(_kode[0].parent.parent)

# Checkpoint RUN 2C memuat val_acc_per_mode; keluaran RUN 2B tidak. Pembeda itu
# dipakai untuk menolak zip yang keliru, bukan sekadar mencocokkan nama berkas.
SEMUA = sorted(Path("/kaggle/input").rglob("fusion_v1_p*_s*.pth"))
print("RFFNET =", RFFNET)
print("KODE   =", KODE)
print(f"\ncheckpoint fusi terpasang: {len(SEMUA)}")
print(f"{'berkas':>34s} {'asal':>8s} {'epoch':>6s} {'kriteria':>18s}")
print("-" * 70)

KANDIDAT = []
for c in SEMUA:
    try:
        d = _t.load(c, map_location="cpu", weights_only=False)
    except Exception as e:
        print(f"{c.name:>34s}  GAGAL DIBACA: {e}")
        continue
    asal = "RUN 2C" if d.get("val_acc_per_mode") is not None else "RUN 2B"
    print(f"{c.name:>34s} {asal:>8s} {str(d.get('epoch')):>6s} "
          f"{str(d.get('selection_criterion')):>18s}")
    if asal == "RUN 2C" and "ENCLAMA" not in c.name and f"_{P_TERPILIH}_" in c.name:
        KANDIDAT.append(c)

if not KANDIDAT:
    raise FileNotFoundError("\n".join([
        "", "=" * 70,
        f"Tidak ada checkpoint {P_TERPILIH} keluaran RUN 2C.",
        "=" * 70,
        "Zip RUN 2B tidak boleh dipakai: checkpoint-nya dipilih dengan akurasi",
        "fusi kondisi bersih yang jenuh, sehingga akurasi termal-saja berayun",
        "48 sampai 98 persen antar-benih. Zip itu juga memang tidak memuat",
        "fusion_v1_p02_s42.pth, karena berkas itu tertimpa run encoder LAMA",
        "lalu diganti nama menjadi _ENCLAMA sebelum penyimpanan.",
        "",
        "Yang harus dilakukan:",
        "  1. Unduh stage2c_hasil.zip dari Output notebook RUN 2C.",
        "  2. Unggah sebagai dataset baru, mis. ckpt-fusion-sweep-2c.",
        "  3. Pasang di Input notebook ini, lepas ckpt-fusion-sweep lama.",
        "",
    ]))

# Setel True HANYA bila waktu benar-benar mepet. Konsekuensinya: Ablation #2
# kembali menjadi angka satu run, dan harus ditulis begitu di slide.
SATU_SAJA = False
if SATU_SAJA:
    KANDIDAT = KANDIDAT[:1]

print(f"\ndipakai: {len(KANDIDAT)} checkpoint dasar")
for c in KANDIDAT:
    print("   ", c.name)
if len(KANDIDAT) < 3 and not SATU_SAJA:
    print(f"\nPERINGATAN: hanya {len(KANDIDAT)} benih. Simpangan dari dua run atau")
    print("kurang bukan penduga yang dapat dipercaya.")

# %% [markdown]
# ## Sel 2 — Salin kode, siapkan config

# %%
import shutil, pathlib, yaml, os, torch

REPO = pathlib.Path("/kaggle/working/repo")
if REPO.exists():
    shutil.rmtree(REPO)
shutil.copytree(KODE, REPO)
os.chdir(REPO)

_tr = pathlib.Path("src/train.py").read_text(encoding="utf-8")
for penanda in ("[PATCH P9]", "[PATCH P10]"):
    assert penanda in _tr, f"{penanda} tidak ada di kode. Pasang v5."
print("penjaga kode: P9 dan P10 terdeteksi")

pathlib.Path("weights_final").mkdir(exist_ok=True)
for c in KANDIDAT:
    d = torch.load(c, map_location="cpu", weights_only=False)
    assert "module." not in list(d["fusion"].keys())[0], f"{c.name}: kunci berprefiks module."
    pm = d["val_acc_per_mode"]
    print(f"  {c.name}: epoch {d.get('epoch')}, termal {pm.get('termal'):.4f}")

p = pathlib.Path("configs/stage5_gating.yaml")
cfg = yaml.safe_load(p.read_text())
cfg["data"]["rffnet_root"] = RFFNET
cfg["model"]["base_checkpoint"] = "weights_final/fusion_v1.pth"
cfg["run_id"] = "stage5_20260827_gating"
cfg["checkpoint"]["out_dir"] = "runs/stage5_20260827_gating"
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
print("\nconfig siap")

# %% [markdown]
# ## Sel 3 — Patch runtime: simpan prediksi per sampel Ablation #2
#
# Tanpa ini, bila kelak ditemukan lagi masalah label, satu-satunya jalan
# memperbaiki `ablation2_gating.csv` adalah melatih ulang. Dengan ini, cukup
# dihitung ulang dari prediksi yang tersimpan.
#
# Nama berkasnya diturunkan dari `ablation2.output_csv`, yang sudah memuat sufiks
# benih. Tanpa itu ketiga run saling menimpa prediksinya, persis kesalahan yang
# merusak RUN 2B.

# %%
import pathlib, py_compile

f = pathlib.Path("src/train.py")
s = f.read_text(encoding="utf-8")

GANTI = [
 ("inisialisasi",
  """    ablation_rows = []
    for tau in [0.0, 0.3, 0.6, 1.0]:
        correct_no_gate, correct_with_gate, total = 0, 0, 0""",
  """    ablation_rows = []
    for tau in [0.0, 0.3, 0.6, 1.0]:
        correct_no_gate, correct_with_gate, total = 0, 0, 0
        per_sample = []   # [PATCH RUN4]"""),
 ("kumpulkan",
  """                correct_no_gate += int(pred_no_gate == label)
                correct_with_gate += int(pred_with_gate == label)
                total += 1""",
  """                correct_no_gate += int(pred_no_gate == label)
                correct_with_gate += int(pred_with_gate == label)
                total += 1
                per_sample.append({"frame_index": fid, "label_true": label,
                                   "pred_no_gate": pred_no_gate,
                                   "pred_with_gate": pred_with_gate})   # [PATCH RUN4]"""),
 ("simpan",
  """        ablation_rows.append({"tau": tau, "acc_no_gate": correct_no_gate / total, "acc_with_gate": correct_with_gate / total})""",
  """        ablation_rows.append({"tau": tau, "acc_no_gate": correct_no_gate / total, "acc_with_gate": correct_with_gate / total})
        import csv as _csv_ps   # [PATCH RUN4]
        _out = Path(config["ablation2"]["output_csv"])
        _ps = _out.parent / f"per_sample_{_out.stem}_tau{tau}.csv"
        _ps.parent.mkdir(parents=True, exist_ok=True)
        with open(_ps, "w", newline="", encoding="utf-8") as _fh:
            _w = _csv_ps.DictWriter(_fh, fieldnames=list(per_sample[0].keys()))
            _w.writeheader(); _w.writerows(per_sample)
        print(f"[Stage5][Ablation2] prediksi per sampel -> {_ps}")"""),
]

for nama, lama, baru in GANTI:
    assert s.count(lama) == 1, f"pola '{nama}' ditemukan {s.count(lama)}x, diharapkan 1"
    s = s.replace(lama, baru)

f.write_text(s, encoding="utf-8")
py_compile.compile("src/train.py", doraise=True)
print("patch RUN4 diterapkan, 3 penggantian, sintaks OK")

# %% [markdown]
# ## Sel 4 — Jalankan Stage 5 untuk tiap checkpoint dasar
#
# `--seed` memberi sufiks pada `final_path` dan `ablation2.output_csv`, jadi
# ketiga run tidak saling menimpa. Benih Stage 5 disamakan dengan benih Stage 2
# asal checkpoint-nya, supaya satu run berarti satu jalur pipeline yang utuh dan
# simpangan yang dilaporkan mencakup seluruh pipeline.

# %%
import re, shutil, time

t_mulai = time.time()
BENIH = []
for c in KANDIDAT:
    S = int(re.search(r"_s(\d+)", c.stem).group(1))
    BENIH.append(S)
    shutil.copy(c, "weights_final/fusion_v1.pth")     # nama yang dicari config
    print("\n" + "=" * 62)
    print(f"  dasar {c.name} -> Stage 5 benih {S}")
    print("=" * 62)
    cmd = f"python src/train.py --config configs/stage5_gating.yaml --seed {S}"
    !{cmd}

print(f"\n{len(KANDIDAT)} run selesai dalam {(time.time()-t_mulai)/60:.1f} menit")

# %% [markdown]
# ## Sel 5 — SIMPAN SEKARANG
#
# Sengaja ditaruh sebelum semua pemeriksaan. Dengan Save & Run All, satu galat di
# sel pelaporan akan menggagalkan seluruh versi dan zip tidak pernah terbentuk.
# Pekerjaan yang sudah selesai tidak boleh bergantung pada mulusnya pelaporan.

# %%
import shutil, os, pathlib

OUT = pathlib.Path("/kaggle/working/keluaran")
if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "weights_final").mkdir(parents=True)
shutil.copytree("reports", OUT / "reports")

# RUN 5 mencari nama fusion_v2_gated.pth tanpa sufiks
utama = pathlib.Path(f"weights_final/fusion_v2_gated_s{BENIH[0]}.pth")
shutil.copy(utama, OUT / "weights_final" / "fusion_v2_gated.pth")
print(f"{utama.name} -> fusion_v2_gated.pth  (yang dicari RUN 5)")
for S in BENIH[1:]:
    src = pathlib.Path(f"weights_final/fusion_v2_gated_s{S}.pth")
    if src.exists():
        shutil.copy(src, OUT / "weights_final" / src.name)

def buat_zip():
    shutil.make_archive("/kaggle/working/stage5_hasil", "zip", OUT)
    return os.path.getsize("/kaggle/working/stage5_hasil.zip") / 1024 ** 2

print(f"\nstage5_hasil.zip : {buat_zip():.1f} MB")
for q in sorted((OUT / "weights_final").glob("*.pth")):
    print("  ", q.name, round(q.stat().st_size / 1024 ** 2, 1), "MB")
print(f"  CSV ablation2 : {len(list((OUT / 'reports').glob('ablation2_gating_s*.csv')))}")
print(f"  per-sampel    : {len(list((OUT / 'reports').glob('per_sample_ablation2_*.csv')))}")
print("\nHASIL SUDAH AMAN. Sel berikutnya hanya pelaporan, tidak dapat merusaknya.")

# %% [markdown]
# ## Sel 6 — Smoke test kontrak API
#
# **`train.py` tidak menulis berkas ini.** `smoke_test_output` tercantum di
# `configs/stage5_gating.yaml` tetapi tidak ada satu pun kode di `src/` yang
# membacanya; berkasnya dihasilkan `src/evaluate.py` sebagai perintah terpisah.
# Ini cacat "tertulis di config, tak pernah diimplementasikan" yang keempat,
# setelah AMP, grid p, dan penguncian benih.
#
# Kegagalannya tidak membatalkan apa pun: ia contoh keluaran kontrak API, bukan
# hasil eksperimen.

# %%
S0 = BENIH[0]
cmd = (f"python src/evaluate.py --checkpoint weights_final/fusion_v2_gated_s{S0}.pth"
       f" --rffnet-root {RFFNET} --mode smoke_test --split val --with-gate"
       f" --out reports/sample_output_stage5.json")
print(cmd)
!{cmd}

# %%
try:
    import json, pathlib
    q = pathlib.Path("reports/sample_output_stage5.json")
    if q.exists():
        d = json.load(open(q, encoding="utf-8"))
        WAJIB = ["alert_id", "timestamp", "location", "prediction",
                 "modality_reliability", "localization", "images",
                 "source_trigger", "operator_decision"]
        kurang = [k for k in WAJIB if k not in d]
        print(f"medan kontrak terpenuhi : {len(WAJIB)-len(kurang)}/{len(WAJIB)}")
        if kurang:
            print(f"belum ada               : {kurang}")
        print(f"modality_reliability    : {d.get('modality_reliability')}")
        shutil.copy(q, OUT / "reports" / q.name)
        print(f"\nzip diperbarui: {buat_zip():.1f} MB")
    else:
        print("smoke test tidak terbentuk. Catat di repo, jangan hambat langkah berikutnya.")
except Exception as e:
    print("sel smoke test gagal, diabaikan:", e)

# %% [markdown]
# ## Sel 7 — Ablation #2, rerata dan simpangan
#
# Acuan semifinal: gating **tidak** meningkatkan akurasi, dan pada tau 0,6 justru
# lebih rendah satu sampel. Nilai gating yang dapat dipertahankan bersifat
# operasional, yaitu mengisi `modality_reliability` pada kontrak API dan badge
# modalitas di konsol operator, bukan menaikkan akurasi.

# %%
try:
    import csv, pathlib, statistics as st

    per_tau, ditemukan = {}, 0
    for S in BENIH:
        q = pathlib.Path(f"reports/ablation2_gating_s{S}.csv")
        if not q.exists():
            print(f"benih {S}: berkas tidak ada")
            continue
        ditemukan += 1
        for r in csv.DictReader(open(q, encoding="utf-8")):
            t = float(r["tau"])
            per_tau.setdefault(t, {"no": [], "yes": []})
            per_tau[t]["no"].append(float(r["acc_no_gate"]) * 100)
            per_tau[t]["yes"].append(float(r["acc_with_gate"]) * 100)

    print(f"{'tau':>5s} {'tanpa gate':>15s} {'dengan gate':>15s} {'selisih':>15s} {'sampel':>8s}")
    print("-" * 64)
    baris = []
    for t in sorted(per_tau):
        a, b = per_tau[t]["no"], per_tau[t]["yes"]
        d = [y - x for x, y in zip(a, b)]
        sa = st.stdev(a) if len(a) > 1 else 0.0
        sb = st.stdev(b) if len(b) > 1 else 0.0
        sd = st.stdev(d) if len(d) > 1 else 0.0
        print(f"{t:5.1f} {st.mean(a):8.2f}+/-{sa:4.2f} {st.mean(b):8.2f}+/-{sb:4.2f} "
              f"{st.mean(d):+8.2f}+/-{sd:4.2f} {st.mean(d)/100*240:7.2f}")
        baris.append({"tau": t, "acc_no_gate_mean": st.mean(a) / 100, "acc_no_gate_std": sa / 100,
                      "acc_with_gate_mean": st.mean(b) / 100, "acc_with_gate_std": sb / 100,
                      "delta_mean": st.mean(d) / 100, "delta_std": sd / 100, "n_run": len(a)})

    with open("reports/ablation2_gating_RERATA.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(baris[0].keys()))
        w.writeheader(); w.writerows(baris)
    shutil.copy("reports/ablation2_gating_RERATA.csv", OUT / "reports")

    tau_urut = sorted(per_tau)
    rer = [st.mean(per_tau[t]["no"]) for t in tau_urut]
    monoton = all(rer[i] >= rer[i + 1] - 1e-9 for i in range(len(rer) - 1))
    print(f"\nturun tau 0 ke 1 : {rer[0]-rer[-1]:.2f} poin")
    print(f"monoton menurun  : {'YA' if monoton else 'TIDAK'}")
    print("Di paper semifinal kurva degradasi MEMBALIK. Bila di sini menurun,")
    print("itu konsisten dengan dugaan bahwa pembalikan adalah artefak seleksi")
    print("model, bukan sifat arsitektur fusi.")

    print("\nBACAAN. Selisih yang lebih kecil daripada simpangannya BUKAN efek.")

    ps = sorted(pathlib.Path("reports").glob("per_sample_ablation2_gating_s*_tau*.csv"))
    print(f"\nberkas per-sampel: {len(ps)}  (harus {4*ditemukan})")

    print(f"\nzip final: {buat_zip():.1f} MB")
except Exception as e:
    print("sel pelaporan gagal, diabaikan. Zip sudah aman sejak Sel 5:", e)

# %% [markdown]
# ## Langkah berikutnya
#
# 1. Panel kanan, `Output`, unduh `stage5_hasil.zip`.
# 2. Unggah sebagai dataset Kaggle bernama **`ckpt-fusion-gated`**.
# 3. Pasang di RUN 5 bersama `kode-orang-a-patched-v5` dan `abangbuan/flame2`.
