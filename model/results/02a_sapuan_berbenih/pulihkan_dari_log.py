"""Pulihkan angka Ablation #1 RUN 2B dari log.

Berkas CSV untuk p=0,2 encoder BARU HILANG: sel A/B menjalankan encoder LAMA
dengan nama keluaran yang sama persis, jadi ia menimpa lebih dulu, baru diganti
nama menjadi _ENCLAMA sesudahnya. Sufiks benih mencegah tabrakan ANTAR-BENIH,
tetapi identitas encoder tidak ikut masuk ke nama berkas, jadi tabrakan
ANTAR-ENCODER tetap terjadi. Angka di bawah disalin dari log run yang tercetak.
"""
import csv, statistics as st
from pathlib import Path

DATA = {
    ("BARU", 0.1, 42): (0.9833, 0.9833, 0.9208),
    ("BARU", 0.1, 43): (1.0000, 0.7500, 0.9458),
    ("BARU", 0.1, 44): (1.0000, 0.9833, 0.8542),
    ("BARU", 0.2, 42): (1.0000, 0.9833, 0.5125),
    ("BARU", 0.2, 43): (1.0000, 0.9833, 0.9167),
    ("BARU", 0.2, 44): (1.0000, 1.0000, 0.4833),
    ("BARU", 0.3, 42): (1.0000, 0.9250, 0.9750),
    ("BARU", 0.3, 43): (0.9958, 0.9833, 0.6417),
    ("BARU", 0.3, 44): (0.9917, 0.9833, 0.8917),
    ("LAMA", 0.2, 42): (0.9833, 0.9833, 0.9625),
    ("LAMA", 0.2, 43): (1.0000, 0.9833, 0.5583),
    ("LAMA", 0.2, 44): (1.0000, 0.9833, 0.9500),
}
EPOCH_TERPILIH = {
    ("BARU", 0.1, 42): 1, ("BARU", 0.1, 43): 8, ("BARU", 0.1, 44): 11,
    ("BARU", 0.2, 42): 20, ("BARU", 0.2, 43): 9, ("BARU", 0.2, 44): 20,
    ("BARU", 0.3, 42): 8, ("BARU", 0.3, 43): 12, ("BARU", 0.3, 44): 9,
    ("LAMA", 0.2, 42): 12, ("LAMA", 0.2, 43): 17, ("LAMA", 0.2, 44): 7,
}

with open("ablation1_run2b_PULIH.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["encoder", "p", "seed", "epoch_terpilih", "fusi", "rgb_saja", "termal_saja", "sumber"])
    for (enc, p, s), (fu, rg, te) in sorted(DATA.items()):
        w.writerow([enc, p, s, EPOCH_TERPILIH[(enc, p, s)], fu, rg, te, "log RUN 2B"])

def ring(sel):
    v = [DATA[k][sel] for k in DATA if k in DATA]
    return v

def stat(keys, sel):
    v = [DATA[k][sel] * 100 for k in keys]
    return st.mean(v), (st.stdev(v) if len(v) > 1 else 0.0), min(v), max(v)

print("ABLATION #1 dan #3 -- tiga benih, encoder BARU")
print(f"{'p':>4s} | {'fusi':>16s} | {'RGB saja':>16s} | {'termal saja':>16s}")
print("-" * 62)
for p in (0.1, 0.2, 0.3):
    k = [("BARU", p, s) for s in (42, 43, 44)]
    sel = [f"{stat(k, i)[0]:6.2f} +/- {stat(k, i)[1]:5.2f}" for i in range(3)]
    print(f"{p:4.1f} | {sel[0]:>16s} | {sel[1]:>16s} | {sel[2]:>16s}")

print("\nA/B ENCODER TERMAL pada p = 0,2 -- tiga benih masing-masing")
print(f"{'encoder':>8s} | {'fusi':>16s} | {'RGB saja':>16s} | {'termal saja':>16s} | rentang termal")
print("-" * 92)
for enc in ("LAMA", "BARU"):
    k = [(enc, 0.2, s) for s in (42, 43, 44)]
    sel = [f"{stat(k, i)[0]:6.2f} +/- {stat(k, i)[1]:5.2f}" for i in range(3)]
    m = stat(k, 2)
    print(f"{enc:>8s} | {sel[0]:>16s} | {sel[1]:>16s} | {sel[2]:>16s} | {m[2]:.2f} sampai {m[3]:.2f}")

mb, sb = stat([("BARU", 0.2, s) for s in (42, 43, 44)], 2)[:2]
ml, sl = stat([("LAMA", 0.2, s) for s in (42, 43, 44)], 2)[:2]
gab = ((sb ** 2 + sl ** 2) / 2) ** 0.5
print(f"\nselisih termal-saja BARU dikurangi LAMA : {mb - ml:+.2f} poin")
print(f"simpangan gabungan                      : {gab:.2f} poin")
print(f"rasio |selisih| / simpangan             : {abs(mb - ml) / gab:.2f}x")
print("\nKlaim RUN 2 satu benih adalah +44,60 poin. Dengan tiga benih arahnya")
print("TERBALIK dan besarnya jauh di dalam derau. Klaim itu gugur.")

print("\n" + "=" * 62)
print("VARIANSI PER MODE, digabung seluruh 12 run")
print("=" * 62)
for i, nama in enumerate(["fusi", "rgb_saja", "termal_saja"]):
    v = [d[i] * 100 for d in DATA.values()]
    print(f"{nama:>12s}: rentang {min(v):6.2f} sampai {max(v):6.2f}  "
          f"lebar {max(v)-min(v):5.2f} poin  simpangan {st.stdev(v):5.2f}")
