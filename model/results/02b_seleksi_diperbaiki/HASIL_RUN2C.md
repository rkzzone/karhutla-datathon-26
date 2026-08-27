# Hasil RUN 2C — hasil nol termal di semifinal adalah artefak seleksi model

Skenario C berangkat dari dugaan bahwa encoder termal Stage 1 rusak, dan itulah
sebab jalur termal tidak berkontribusi di babak semifinal. **Dugaan itu salah.**
Penyebabnya adalah kriteria seleksi model, dan RUN 2C membuktikannya dengan tiga
bukti bebas yang saling menguatkan.

---

## 1. Simpangan antar-benih runtuh

Kriteria seleksi diganti dari akurasi fusi kondisi bersih menjadi rerata akurasi
tiga mode ketersediaan modalitas (P9). Tidak ada perubahan lain: data, arsitektur,
hiperparameter, dan benih semuanya sama.

| kelompok | mode | RUN 2B | RUN 2C | faktor |
|---|---|---|---|---|
| p=0,1 | termal saja | 90,69 ± 4,73 | 95,00 ± 2,17 | 2,2x |
| p=0,2 | termal saja | 63,75 ± **24,22** | 96,67 ± **1,82** | **13,3x** |
| p=0,3 | termal saja | 83,61 ± 17,35 | 96,67 ± 2,17 | 8,0x |
| ENCLAMA | termal saja | 82,36 ± 22,98 | 96,95 ± 1,34 | 17,2x |
| p=0,1 | RGB saja | 90,55 ± 13,47 | 98,05 ± 0,48 | 28,1x |

Yang tidak stabil memang **pilihan epoch**, bukan pelatihannya.

---

## 2. Bukti langsung dari log per-epoch

Kolom `val_acc` adalah kriteria seleksi lama.

**encoder LAMA, benih 42.** Ini demonstrasi terkontrol: satu run, satu lintasan
bobot, hanya kriterianya yang berbeda.

| epoch | fusi | rgb | termal | |
|---|---|---|---|---|
| 7 | 0,9875 | 0,9833 | **0,9792** | dipilih oleh **P9** |
| 8 | 0,9792 | 0,9792 | 0,9792 | |
| 9 | 0,9792 | 0,9917 | 0,7458 | |
| 10 | **1,0000** | 0,9833 | **0,5958** | dipilih oleh **kriteria lama** |
| 11 | 0,9625 | 0,9833 | 0,5875 | |

Kriteria seleksi saja menggeser akurasi termal-saja sebesar **38,3 poin**.

**p=0,2 benih 42, epoch 10.** Akurasi fusi 0,9792 dan RGB 0,9833, keduanya nyaris
sempurna, sementara jalur termal runtuh ke **0,2667**, yaitu di bawah tebakan acak
tiga kelas. Model yang menurut kriteria lama nyaris tak bercacat sudah kehilangan
satu modalitas sepenuhnya, dan kriteria itu sama sekali tidak melihatnya.

**p=0,3 benih 44, epoch 21 sampai 32.** Akurasi fusi tetap 1,0000 di dua belas
epoch berturut, sementara jalur termal jatuh 14,2 poin. Kriteria lama melihat dua
belas seri sempurna dan memilih di antaranya secara sembarang.

---

## 3. Epoch terpilih bergeser ke awal

Epoch terpilih pada RUN 2C: 1, 2, 2, 2, 2, 4, 5, 7, 8, 8, 9, 22. Median 4.

Jalur unimodal **memburuk seiring pelatihan berlanjut**, walaupun akurasi fusi
kondisi bersih tetap naik atau bertahan. Ini overfitting yang sepenuhnya tak
terlihat oleh kriteria lama: model belajar bersandar pada gabungan kedua
modalitas dan berhenti mempertahankan kemampuan tiap jalur secara mandiri, justru
kemampuan yang menjadi seluruh alasan memakai modality dropout.

---

## 4. Pertukarannya, dan angkanya

Rerata seluruh 12 run:

| mode | RUN 2B | RUN 2C | selisih | simpangan |
|---|---|---|---|---|
| fusi | 99,62 | 98,64 | **−0,97** | 0,65 → 0,64 |
| RGB saja | 96,04 | 98,23 | +2,19 | 6,86 → 0,26 |
| termal saja | 80,10 | 96,32 | **+16,22** | 19,23 → **1,81** |

Menyerahkan 0,97 poin akurasi kondisi bersih, memperoleh 16,22 poin pada jalur
termal dan simpangan yang mengecil sepuluh kali lipat. Untuk sistem yang klaimnya
ketahanan modalitas, ini pertukaran yang benar, dan sekarang ada angkanya.

---

## 5. Dua pertanyaan yang kini terjawab tuntas

### A/B encoder termal: tidak ada beda yang terdeteksi

| mode | BARU (Stage 1 val 0,9758) | LAMA (Stage 1 val 0,5148) | selisih | rasio terhadap derau |
|---|---|---|---|---|
| fusi | 98,33 ± 0,00 | 98,47 ± 0,24 | −0,14 | 0,82x |
| RGB saja | 98,33 ± 0,00 | 98,33 ± 0,00 | 0,00 | 0,00x |
| termal saja | 96,67 ± 1,82 | 96,95 ± 1,34 | −0,28 | 0,18x |

Selisih akurasi Stage 1 sebesar 46 poin **tidak menghasilkan beda apa pun di
hilir.** Sejalan dengan `train.py:283`, yang memasukkan seluruh parameter encoder
termal ke optimizer Stage 2: encoder itu dilatih ulang sepenuhnya di RFFNet, jadi
bobot Stage 1 hanyalah titik awal yang ditimpa.

Perbaikan RUN 1, yakni P5, P6, dan P7, tetap **benar dan wajib**, karena `val_acc`
Stage 1 yang lama memang tidak dapat ditafsirkan. Tetapi jangan dibingkai sebagai
sumber perbaikan performa. Ia perbaikan kebenaran pengukuran, bukan perbaikan
hasil.

### Ablation #3: p tidak dapat dibedakan pada akurasi kondisi bersih

| p | fusi | RGB saja | termal saja |
|---|---|---|---|
| 0,1 | 98,89 ± 0,96 | 98,05 ± 0,48 | 95,00 ± 2,17 |
| 0,2 | 98,33 ± 0,00 | 98,33 ± 0,00 | 96,67 ± 1,82 |
| 0,3 | 98,89 ± 0,96 | 98,19 ± 0,24 | 96,67 ± 2,17 |

Rentang rerata antar-p 1,67 poin, simpangan khas dalam satu p 2,05 poin, rasio
0,81. **Laporkan apa adanya:** pada rentang yang diuji, `p` tidak berpengaruh
terhadap akurasi kondisi bersih. `p = 0,2` dipertahankan karena tidak ada pembeda
yang melewati derau, bukan karena ia menang.

Pembeda yang sesungguhnya, bila ada, harus muncul di kurva degradasi. Itu Sel 8.

---

## 6. Nilainya untuk babak final

Ini bukan sekadar koreksi rumah tangga. Ia temuan metodologis yang bisa
dipertahankan di depan juri:

> Pada tolok ukur yang jenuh, memilih model berdasarkan akurasi kondisi bersih
> merusak jalur unimodal secara diam-diam. Untuk sistem multimodal yang klaimnya
> ketahanan, kriteria seleksi harus berupa akurasi harapan di seluruh kondisi
> ketersediaan modalitas. Selisihnya 16 poin pada jalur termal, dan sampai 38 poin
> pada satu run yang lintasan bobotnya identik.

Ia juga menjelaskan tiga hal yang di paper semifinal hanya bisa dilaporkan tanpa
sebab: hasil nol termal, kurva degradasi yang membalik, dan ketidakstabilan
antar-run. Ketiganya berasal dari satu akar yang sekarang teridentifikasi dan
tertambal.

**Yang tidak boleh diklaim:** bahwa encoder termal baru lebih baik, bahwa satu
nilai `p` lebih baik, atau bahwa sistemnya sekarang lebih akurat. Akurasi kondisi
bersih justru **turun** 0,97 poin. Yang meningkat adalah ketahanan dan
keterulangan.

---

## 7. Sel 8 sudah masuk, dan ia menutup argumennya

Lihat [`KURVA_DEGRADASI.md`](KURVA_DEGRADASI.md). Ringkasnya:

- **Delapan dari delapan kurva berakhir lebih rendah daripada awalnya.** Tidak
  ada pembalikan di mana pun.
- **Baris LAMA juga tidak membalik.** Itu memakai encoder Stage 1 yang sama
  dengan babak semifinal. Encoder sama, hanya kriteria seleksi diganti, dan
  pembalikan lenyap. Rantai sebabnya kini tertutup.
- **Kehilangan termal sepenuhnya berbiaya sekitar 5 poin** pada partisi uji.
- **Jurang val ke test sekitar 12 poin.** Angka val dilarang masuk slide.
- p tetap tidak dapat dibedakan, dan urutannya bahkan berbeda antara val dan
  test, tanda khas peringkat yang digerakkan derau.
