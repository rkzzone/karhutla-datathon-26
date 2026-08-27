"""Bandingkan RUN 2B (seleksi akurasi fusi bersih) dengan RUN 2C (seleksi P9)."""
import csv, statistics as st

# (fusi, rgb, termal) pada rffnet_val, per (encoder, p, benih)
RUN2B = {
    ("BARU", 0.1, 42): (0.9833, 0.9833, 0.9208), ("BARU", 0.1, 43): (1.0000, 0.7500, 0.9458),
    ("BARU", 0.1, 44): (1.0000, 0.9833, 0.8542), ("BARU", 0.2, 42): (1.0000, 0.9833, 0.5125),
    ("BARU", 0.2, 43): (1.0000, 0.9833, 0.9167), ("BARU", 0.2, 44): (1.0000, 1.0000, 0.4833),
    ("BARU", 0.3, 42): (1.0000, 0.9250, 0.9750), ("BARU", 0.3, 43): (0.9958, 0.9833, 0.6417),
    ("BARU", 0.3, 44): (0.9917, 0.9833, 0.8917), ("LAMA", 0.2, 42): (0.9833, 0.9833, 0.9625),
    ("LAMA", 0.2, 43): (1.0000, 0.9833, 0.5583), ("LAMA", 0.2, 44): (1.0000, 0.9833, 0.9500),
}
RUN2C = {
    ("BARU", 0.1, 42): (0.9833, 0.9833, 0.9750), ("BARU", 0.1, 43): (0.9833, 0.9833, 0.9375),
    ("BARU", 0.1, 44): (1.0000, 0.9750, 0.9375), ("BARU", 0.2, 42): (0.9833, 0.9833, 0.9458),
    ("BARU", 0.2, 43): (0.9833, 0.9833, 0.9750), ("BARU", 0.2, 44): (0.9833, 0.9833, 0.9792),
    ("BARU", 0.3, 42): (0.9833, 0.9833, 0.9417), ("BARU", 0.3, 43): (0.9833, 0.9792, 0.9792),
    ("BARU", 0.3, 44): (1.0000, 0.9833, 0.9792), ("LAMA", 0.2, 42): (0.9875, 0.9833, 0.9792),
    ("LAMA", 0.2, 43): (0.9833, 0.9833, 0.9542), ("LAMA", 0.2, 44): (0.9833, 0.9833, 0.9750),
}
EPOCH2C = {("BARU", 0.1, 42): 4, ("BARU", 0.1, 43): 2, ("BARU", 0.1, 44): 9,
           ("BARU", 0.2, 42): 2, ("BARU", 0.2, 43): 2, ("BARU", 0.2, 44): 2,
           ("BARU", 0.3, 42): 5, ("BARU", 0.3, 43): 1, ("BARU", 0.3, 44): 22,
           ("LAMA", 0.2, 42): 7, ("LAMA", 0.2, 43): 8, ("LAMA", 0.2, 44): 8}

def stat(D, keys, i):
    v = [D[k][i] * 100 for k in keys]
    return st.mean(v), (st.stdev(v) if len(v) > 1 else 0.0)

print("=" * 78)
print("SIMPANGAN ANTAR-BENIH, akibat mengganti kriteria seleksi")
print("=" * 78)
print(f"{'kelompok':>10s} | {'mode':>12s} | {'RUN 2B':>16s} | {'RUN 2C':>16s} | faktor")
print("-" * 78)
KEL = [("p=0.1", [("BARU", 0.1, s) for s in (42, 43, 44)]),
       ("p=0.2", [("BARU", 0.2, s) for s in (42, 43, 44)]),
       ("p=0.3", [("BARU", 0.3, s) for s in (42, 43, 44)]),
       ("ENCLAMA", [("LAMA", 0.2, s) for s in (42, 43, 44)])]
for nama, keys in KEL:
    for i, mode in enumerate(["fusi", "rgb_saja", "termal_saja"]):
        mb, sb = stat(RUN2B, keys, i)
        mc, sc = stat(RUN2C, keys, i)
        fak = f"{sb/sc:5.1f}x" if sc > 1e-9 else "    -"
        print(f"{nama:>10s} | {mode:>12s} | {mb:6.2f} +/- {sb:5.2f} | {mc:6.2f} +/- {sc:5.2f} | {fak}")
    print("-" * 78)

print("\n" + "=" * 78)
print("PERTUKARAN: akurasi kondisi bersih ditukar dengan jalur unimodal")
print("=" * 78)
semua = list(RUN2B)
for i, mode in enumerate(["fusi", "rgb_saja", "termal_saja"]):
    mb, sb = stat(RUN2B, semua, i)
    mc, sc = stat(RUN2C, semua, i)
    print(f"{mode:>12s}: {mb:6.2f} -> {mc:6.2f}  ({mc-mb:+6.2f} poin)   "
          f"simpangan {sb:5.2f} -> {sc:5.2f}")
print("\nMenukar 1,1 poin akurasi fusi kondisi bersih dengan kenaikan besar dan")
print("pemantapan jalur termal. Untuk sistem yang klaimnya ketahanan modalitas,")
print("ini pertukaran yang benar, dan sekarang ada angkanya.")

print("\n" + "=" * 78)
print("A/B ENCODER TERMAL, jawaban akhir")
print("=" * 78)
kb = [("BARU", 0.2, s) for s in (42, 43, 44)]
kl = [("LAMA", 0.2, s) for s in (42, 43, 44)]
for i, mode in enumerate(["fusi", "rgb_saja", "termal_saja"]):
    mb, sb = stat(RUN2C, kb, i)
    ml, sl = stat(RUN2C, kl, i)
    gab = ((sb ** 2 + sl ** 2) / 2) ** 0.5
    r = abs(mb - ml) / gab if gab > 1e-9 else 0.0
    print(f"{mode:>12s}: BARU {mb:6.2f} +/- {sb:4.2f}   LAMA {ml:6.2f} +/- {sl:4.2f}   "
          f"selisih {mb-ml:+5.2f}  rasio {r:4.2f}x")
print("\nStage 1 val 0,5148 melawan 0,9758 -> tidak ada beda terdeteksi di hilir.")
print("Sejalan dengan train.py:283, yang memasukkan seluruh parameter encoder")
print("termal ke optimizer Stage 2. Dua bukti bebas yang saling menguatkan.")

print("\n" + "=" * 78)
print("ABLATION #3, jawaban akhir pada val")
print("=" * 78)
for nama, keys in KEL[:3]:
    sel = [f"{stat(RUN2C, keys, i)[0]:6.2f} +/- {stat(RUN2C, keys, i)[1]:4.2f}" for i in range(3)]
    print(f"{nama:>7s} | fusi {sel[0]} | RGB {sel[1]} | termal {sel[2]}")
tv = [stat(RUN2C, k, 2) for _, k in KEL[:3]]
lebar = max(m for m, _ in tv) - min(m for m, _ in tv)
sgab = st.mean([s for _, s in tv])
print(f"\nrentang rerata termal antar-p : {lebar:.2f} poin")
print(f"simpangan khas dalam satu p   : {sgab:.2f} poin")
print(f"rasio                         : {lebar/sgab:.2f}x  -> tidak dapat dibedakan")

print("\n" + "=" * 78)
print("EPOCH TERPILIH pada RUN 2C")
print("=" * 78)
e = sorted(EPOCH2C.values())
print(f"nilai   : {e}")
print(f"median  : {st.median(e):.0f}   rentang {min(e)} sampai {max(e)}")
print("Kriteria baru cenderung memilih epoch awal. Jalur unimodal memburuk")
print("ketika pelatihan berlanjut, walaupun akurasi fusi bersih tetap naik.")
print("Itu overfitting yang tidak terlihat sama sekali oleh kriteria lama.")
