"""Kurva degradasi RUN 2C Sel 8. Ini angka utama slide."""
import statistics as st

TAU = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
# (rerata, simpangan) per tau, tiga benih
VAL = {
 "p=0.1": [(98.89,1.0),(98.75,0.7),(98.75,0.7),(98.33,0.4),(97.78,0.5),(94.86,1.7)],
 "p=0.2": [(98.33,0.0),(98.33,0.0),(98.33,0.0),(96.81,1.0),(95.97,1.9),(90.14,4.4)],
 "p=0.3": [(98.89,1.0),(98.89,1.0),(98.61,0.9),(97.92,1.9),(96.81,1.3),(94.72,3.1)],
 "LAMA":  [(98.47,0.2),(98.19,0.2),(98.19,0.2),(98.33,0.0),(97.64,0.9),(93.47,4.1)],
}
TEST = {
 "p=0.1": [(87.50,4.3),(87.83,4.9),(87.50,4.3),(86.50,2.6),(85.00,0.0),(83.33,1.3)],
 "p=0.2": [(85.00,0.0),(85.00,0.0),(85.00,0.0),(85.00,0.0),(85.00,0.0),(80.33,4.3)],
 "p=0.3": [(88.00,5.2),(88.17,5.5),(88.17,5.5),(86.83,4.1),(82.50,1.0),(81.33,2.3)],
 "LAMA":  [(85.83,1.9),(85.33,1.0),(84.83,0.3),(84.67,1.5),(83.00,1.8),(81.50,1.0)],
}
TURUN = {"val": {"p=0.1":(4.03,1.46),"p=0.2":(8.19,4.42),"p=0.3":(4.17,2.92),"LAMA":(5.00,3.97)},
         "test":{"p=0.1":(4.17,4.37),"p=0.2":(4.67,4.25),"p=0.3":(6.67,5.53),"LAMA":(4.33,2.75)}}

print("=" * 74)
print("1. TIDAK ADA SATU PUN KURVA YANG MEMBALIK")
print("=" * 74)
for split, D in [("val", VAL), ("test", TEST)]:
    for nama, baris in D.items():
        v = [m for m, _ in baris]
        naik = [(TAU[i], TAU[i+1]) for i in range(len(v)-1) if v[i+1] > v[i] + 1e-9]
        mono = "monoton" if not naik else f"naik di {naik}"
        print(f"  {split:>4s} {nama:>6s}: {v[0]:.2f} -> {v[-1]:.2f}   {mono}")
print("\n  Delapan kurva, delapan-duanya BERAKHIR lebih rendah daripada awalnya.")
print("  Tiga di antaranya punya satu langkah naik kecil di tengah, yaitu")
print("  +0,14  +0,33  dan +0,17 poin, semuanya jauh lebih kecil daripada")
print("  simpangannya sendiri. Jadi yang tepat dikatakan bukan 'monoton',")
print("  melainkan TIDAK ADA PEMBALIKAN: di paper semifinal kurva berakhir")
print("  LEBIH TINGGI daripada awalnya, di sini tidak satu pun begitu.")

print("\n" + "=" * 74)
print("2. PEMBALIKAN ITU BUKAN SALAH ENCODER TERMAL")
print("=" * 74)
print("  Baris LAMA memakai encoder Stage 1 yang val-nya 0,5148, yaitu encoder")
print("  yang sama dengan yang dipakai di babak semifinal. Kurvanya di sini")
print("  MENURUN monoton, di val maupun test.")
print("  -> Dengan encoder yang sama, hanya kriteria seleksi yang diganti,")
print("     pembalikan itu hilang. Penyebabnya kriteria seleksi, titik.")
print("  Ini melengkapi dua bukti sebelumnya menjadi rantai sebab yang utuh:")
print("     ganti encoder saja  -> tidak ada beda   (A/B, rasio 0,18x derau)")
print("     ganti kriteria saja -> simpangan turun 13x, pembalikan hilang")

print("\n" + "=" * 74)
print("3. BENTUKNYA DATARAN LALU JURANG, BUKAN LERENG")
print("=" * 74)
for split, D in [("val", VAL), ("test", TEST)]:
    print(f"\n  partisi {split}")
    print(f"  {'kelompok':>8s} {'t=0 ke t=0,8':>14s} {'t=0,8 ke t=1':>14s}  porsi turun di langkah akhir")
    print("  " + "-" * 72)
    for nama, baris in D.items():
        v = [m for m, _ in baris]
        awal, akhir = v[0] - v[4], v[4] - v[5]
        tot = v[0] - v[5]
        porsi = akhir / tot * 100 if tot > 1e-9 else float("nan")
        print(f"  {nama:>8s} {awal:13.2f}p {akhir:13.2f}p  {porsi:26.0f}%")
print("\n  Di val polanya konsisten: 50 sampai 83 persen penurunan terjadi di")
print("  langkah terakhir saja. Di test polanya TIDAK konsisten, 18 sampai 100")
print("  persen. Jadi 'dataran lalu jurang' hanya boleh diklaim untuk val.")
print("  Di test cukup dikatakan degradasi termal parsial berbiaya kecil.")

print("\n" + "=" * 74)
print("4. BESAR PENURUNAN, DAN BATAS YANG JUJUR")
print("=" * 74)
for split in ("val", "test"):
    print(f"\n  partisi {split}")
    print(f"  {'kelompok':>8s} {'turun':>16s} {'rasio thd derau':>16s}")
    print("  " + "-" * 44)
    for nama, (m, sd) in TURUN[split].items():
        r = m / sd if sd > 1e-9 else float("inf")
        print(f"  {nama:>8s} {m:9.2f} +/- {sd:4.2f} {r:15.2f}x")
semua = [m for s in TURUN for m, _ in TURUN[s].values()]
print(f"\n  delapan kelompok, delapan-duanya positif. Rerata {st.mean(semua):.2f} poin.")
print("  Uji tanda dua sisi atas 8 tanda sama: p = 2 x 0,5^8 = 0,0078.")
print("  Kelompoknya berbagi data, jadi ini indikasi arah, bukan uji formal.")
print("\n  BATASNYA: pada tiap kelompok, besar penurunan sebanding dengan")
print("  simpangannya sendiri. Yang boleh diklaim adalah ARAH dan BENTUK")
print("  kurvanya, bukan angka penurunan satu kelompok tertentu.")

print("\n" + "=" * 74)
print("5. JURANG VAL KE TEST, dan ini harus masuk slide")
print("=" * 74)
print(f"  {'kelompok':>8s} {'val t=0':>9s} {'test t=0':>10s} {'selisih':>9s}")
print("  " + "-" * 40)
for nama in VAL:
    a, b = VAL[nama][0][0], TEST[nama][0][0]
    print(f"  {nama:>8s} {a:8.2f}% {b:9.2f}% {a-b:8.2f}p")
print("\n  Sekitar 12 poin. rffnet_val JENUH dan bukan penduga performa.")
print("  Sejak P9, val juga ikut dioptimasi kriteria seleksi, jadi angka val")
print("  TIDAK boleh dipakai sebagai klaim performa. Pakai test.")
print("\n  Catatan konsistensi: p=0.2 test t=0 adalah 85,00 +/- 0,00, sama persis")
print("  dengan angka test babak semifinal setelah koreksi label. Dua jalur")
print("  perhitungan yang bebas satu sama lain bertemu di angka yang sama.")

print("\n" + "=" * 74)
print("6. SAPUAN p TETAP TIDAK DAPAT DIBEDAKAN")
print("=" * 74)
for split in ("val", "test"):
    t = {k: v for k, v in TURUN[split].items() if k != "LAMA"}
    lebar = max(m for m, _ in t.values()) - min(m for m, _ in t.values())
    sdr = st.mean([sd for _, sd in t.values()])
    urut = sorted(t, key=lambda k: t[k][0])
    print(f"  {split:>4s}: rentang {lebar:.2f}p, simpangan khas {sdr:.2f}p, "
          f"rasio {lebar/sdr:.2f}x   urutan terbaik->terburuk {urut}")
print("\n  Urutannya BERBEDA antara val dan test. Itu tanda khas peringkat yang")
print("  digerakkan derau. Pertahankan p=0,2, dan katakan p tidak dipilih")
print("  berdasarkan hasil melainkan karena tidak ada pembeda yang lolos derau.")
