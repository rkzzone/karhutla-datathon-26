import statistics as st

# (tanpa gate, dengan gate) per benih, per tau -- dari log RUN 4
DATA = {
 0.0: [(0.9833, 0.9833), (0.9833, 0.9833), (0.9833, 0.9833)],
 0.3: [(0.9833, 0.9833), (0.9833, 0.9833), (0.9833, 0.9833)],
 0.6: [(0.9625, 0.9625), (0.9625, 0.9625), (0.9792, 0.9792)],
 1.0: [(0.8750, 0.8750), (0.8917, 0.9000), (0.9500, 0.9500)],
}
VAL_LOSS_GATE = {42: (0.1641, 0.1269), 43: (0.1687, 0.1308), 44: (0.1831, 0.1181)}
N = 240

print("ABLATION #2 -- gating, tiga jalur pipeline penuh")
print(f"{'tau':>5s} {'tanpa gate':>15s} {'dengan gate':>15s} {'selisih':>15s} {'sampel':>8s}")
print("-" * 64)
kurva = []
for tau in sorted(DATA):
    a = [x * 100 for x, _ in DATA[tau]]
    b = [y * 100 for _, y in DATA[tau]]
    d = [y - x for x, y in zip(a, b)]
    kurva.append((tau, st.mean(a), st.stdev(a)))
    print(f"{tau:5.1f} {st.mean(a):8.2f}+/-{st.stdev(a):4.2f} {st.mean(b):8.2f}+/-{st.stdev(b):4.2f} "
          f"{st.mean(d):+8.2f}+/-{st.stdev(d):4.2f} {st.mean(d)/100*N:7.2f}")

print("\n1. EFEK GATING TERHADAP AKURASI")
tot = sum(st.mean([y - x for x, y in DATA[t]]) / 100 * N for t in DATA)
print(f"   Total selisih di seluruh tau: {tot:.2f} sampel dari {N} per level.")
print("   Dua dari tiga jalur: selisih NOL persis di keempat level.")
print("   Satu jalur: 2 sampel di tau=1,0 saja.")
print("   -> Gating TIDAK mengubah akurasi. Hasil negatif, kini dengan simpangan")
print("      dan tiga replikasi, bukan satu run seperti di babak semifinal.")

print("\n2. APAKAH GATE-NYA BELAJAR? YA.")
print(f"   {'benih':>6s} {'val_loss awal':>14s} {'val_loss akhir':>15s} {'turun':>8s}")
print("   " + "-" * 47)
for s, (aw, ak) in VAL_LOSS_GATE.items():
    print(f"   {s:6d} {aw:14.4f} {ak:15.4f} {(aw-ak)/aw*100:7.1f}%")
print("   Gate memang mempelajari keandalan modalitas, turun 22 sampai 35 persen.")
print("   Yang tidak terjadi adalah prediksinya mengubah keputusan klasifikasi.")
print("   Rumusan jujurnya: gate INFORMATIF tetapi tidak MENGUBAH KEPUTUSAN.")

print("\n3. KURVANYA MENURUN MONOTON -- ini yang mudah terlewat")
print(f"   {'tau':>5s} {'akurasi':>16s}")
print("   " + "-" * 24)
for tau, m, sd in kurva:
    print(f"   {tau:5.1f} {m:9.2f}+/-{sd:4.2f}")
turun = kurva[0][1] - kurva[-1][1]
monoton = all(kurva[i][1] >= kurva[i+1][1] - 1e-9 for i in range(len(kurva)-1))
print(f"   turun tau 0 ke 1 : {turun:.2f} poin")
print(f"   monoton menurun  : {'YA' if monoton else 'TIDAK'}")
print("   Di paper semifinal kurva degradasi MEMBALIK, yaitu akurasi naik ketika")
print("   modalitas makin didegradasi. Di sini ia menurun sebagaimana mestinya.")
print("   Konsisten dengan dugaan bahwa pembalikan itu artefak seleksi model,")
print("   bukan sifat arsitektur. Konfirmasi penuhnya di Sel 8 RUN 2C.")
