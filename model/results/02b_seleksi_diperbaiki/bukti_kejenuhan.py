"""Bukti langsung dari log per-epoch RUN 2C: kriteria lama buta terhadap
runtuhnya jalur unimodal. Kolom val_acc adalah kriteria seleksi LAMA."""

KASUS = {
 "p=0.3 benih 44, epoch 21 sampai 32": [
   (21, 1.0000, 0.9833, 0.9750), (22, 1.0000, 0.9833, 0.9792),
   (23, 1.0000, 0.9833, 0.9375), (25, 1.0000, 0.9833, 0.9542),
   (27, 1.0000, 0.9833, 0.9042), (30, 1.0000, 0.9833, 0.8500),
   (32, 1.0000, 0.9833, 0.8375)],
 "p=0.2 benih 42, epoch 5 sampai 12": [
   (5, 0.9833, 0.9833, 0.8792), (6, 0.9833, 0.9833, 0.7042),
   (7, 0.9833, 0.9833, 0.7458), (8, 0.9833, 0.9833, 0.7750),
   (10, 0.9792, 0.9833, 0.2667), (12, 0.9833, 0.9708, 0.9417)],
 "encoder LAMA benih 42, epoch 7 sampai 11": [
   (7, 0.9875, 0.9833, 0.9792), (8, 0.9792, 0.9792, 0.9792),
   (9, 0.9792, 0.9917, 0.7458), (10, 1.0000, 0.9833, 0.5958),
   (11, 0.9625, 0.9833, 0.5875)],
}

for judul, baris in KASUS.items():
    print("=" * 70)
    print(judul)
    print("=" * 70)
    print(f"{'epoch':>6s} {'fusi':>8s} {'rgb':>8s} {'termal':>8s}   {'kriteria LAMA':>14s}")
    print("-" * 62)
    fmax = max(r[1] for r in baris)
    for ep, fu, rg, te in baris:
        tanda = "  <- dipilih" if fu >= fmax else ""
        print(f"{ep:6d} {fu:8.4f} {rg:8.4f} {te:8.4f}   {fu:14.4f}{tanda}")
    fs = [r[1] for r in baris]; ts = [r[3] for r in baris]
    print(f"\nrentang fusi   : {min(fs)*100:.2f} sampai {max(fs)*100:.2f}  "
          f"lebar {(max(fs)-min(fs))*100:.2f} poin")
    print(f"rentang termal : {min(ts)*100:.2f} sampai {max(ts)*100:.2f}  "
          f"lebar {(max(ts)-min(ts))*100:.2f} poin")
    print()

print("=" * 70)
print("BACAAN")
print("=" * 70)
print("Pada kasus pertama akurasi fusi TETAP 1,0000 di dua belas epoch berturut,")
print("sementara jalur termal jatuh 14 poin. Kriteria lama melihat dua belas seri")
print("sempurna dan memilih di antaranya secara sembarang.")
print()
print("Kasus kedua paling telak: pada epoch 10 akurasi fusi 0,9792 dan RGB 0,9833,")
print("dua-duanya nyaris sempurna, sementara jalur termal runtuh ke 0,2667, yaitu")
print("DI BAWAH tebakan acak tiga kelas. Model yang menurut kriteria lama hampir")
print("tak bercacat sebenarnya sudah kehilangan satu modalitas sepenuhnya.")
print()
print("Inilah mekanisme yang menghasilkan hasil nol termal di babak semifinal.")
print("Penyebabnya bukan data, bukan arsitektur fusi, bukan mutu pra-pelatihan")
print("Stage 1, melainkan kriteria seleksi model.")
