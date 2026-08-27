# Kurva degradasi RUN 2C — rantai sebab tertutup

Ini angka utama slide. Tiga benih per kelompok, dua partisi, enam level τ.
Kelompok **LAMA** memakai encoder Stage 1 yang sama dengan babak semifinal.

Sumber: Sel 8 `runs/02b_seleksi_diperbaiki.py`. Perhitungan ulang:
[`kurva_degradasi.py`](kurva_degradasi.py).

---

## 1. Temuan utama: pembalikan itu hilang, dan penyebabnya bukan encoder

Di paper semifinal kurva degradasi **membalik** — akurasi naik ketika modalitas
termal makin didegradasi. Di RUN 2C, **delapan dari delapan kurva berakhir lebih
rendah daripada awalnya.**

Tiga kurva punya satu langkah naik kecil di tengah: +0,14 · +0,33 · +0,17 poin,
seluruhnya jauh di bawah simpangannya sendiri. Jadi yang tepat dikatakan bukan
"monoton", melainkan **tidak ada pembalikan**.

**Yang menutup argumennya adalah baris LAMA.** Ia memakai encoder Stage 1 yang
val-nya 0,5148, encoder yang sama dengan babak semifinal, dan kurvanya tetap
turun: 98,47 → 93,47 di val, 85,83 → 81,50 di test. Encoder yang sama, hanya
kriteria seleksi yang diganti, dan pembalikan itu lenyap.

Tiga bukti bebas kini membentuk satu rantai:

| Yang diubah | Akibatnya |
|---|---|
| encoder termal saja (A/B, 46 poin selisih Stage 1) | tidak ada beda, 0,18× derau |
| kriteria seleksi saja (P9) | simpangan termal-saja turun 13× |
| kriteria seleksi saja, encoder LAMA dipertahankan | pembalikan hilang |

**Penyebab hasil nol termal dan kurva membalik di babak semifinal adalah
kriteria seleksi model, bukan data, bukan arsitektur fusi, bukan mutu Stage 1.**

---

## 2. Angka untuk slide — pakai TEST, bukan val

| kelompok | τ=0,0 | τ=0,2 | τ=0,4 | τ=0,6 | τ=0,8 | τ=1,0 | turun |
|---|---|---|---|---|---|---|---|
| p=0,1 | 87,50 ± 4,3 | 87,83 ± 4,9 | 87,50 ± 4,3 | 86,50 ± 2,6 | 85,00 ± 0,0 | 83,33 ± 1,3 | 4,17 ± 4,37 |
| **p=0,2** | **85,00 ± 0,0** | 85,00 ± 0,0 | 85,00 ± 0,0 | 85,00 ± 0,0 | 85,00 ± 0,0 | **80,33 ± 4,3** | 4,67 ± 4,25 |
| p=0,3 | 88,00 ± 5,2 | 88,17 ± 5,5 | 88,17 ± 5,5 | 86,83 ± 4,1 | 82,50 ± 1,0 | 81,33 ± 2,3 | 6,67 ± 5,53 |
| LAMA | 85,83 ± 1,9 | 85,33 ± 1,0 | 84,83 ± 0,3 | 84,67 ± 1,5 | 83,00 ± 1,8 | 81,50 ± 1,0 | 4,33 ± 2,75 |

**Kehilangan modalitas termal sepenuhnya berbiaya sekitar 5 poin akurasi.** Itu
klaim ketahanan yang sesungguhnya, dan sekarang ia terukur dengan simpangan.

---

## 3. Jurang val ke test, dan kenapa val dilarang masuk slide

| kelompok | val τ=0 | test τ=0 | selisih |
|---|---|---|---|
| p=0,1 | 98,89% | 87,50% | 11,39 |
| p=0,2 | 98,33% | 85,00% | 13,33 |
| p=0,3 | 98,89% | 88,00% | 10,89 |
| LAMA | 98,47% | 85,83% | 12,64 |

Sekitar 12 poin. `rffnet_val` jenuh dan bukan penduga performa. Sejak P9 ia juga
ikut dioptimasi kriteria seleksi, jadi **angka val tidak boleh dipakai sebagai
klaim performa sama sekali.**

**Pemeriksaan konsistensi yang menguatkan:** p=0,2 pada test τ=0 adalah
**85,00 ± 0,00** di ketiga benih, sama persis dengan angka test babak semifinal
setelah koreksi label. Dua jalur perhitungan yang bebas satu sama lain bertemu di
angka yang sama.

---

## 4. Batas yang harus dinyatakan terbuka

Pada tiap kelompok, besar penurunan **sebanding dengan simpangannya sendiri**:

| partisi | kelompok | turun | rasio terhadap derau |
|---|---|---|---|
| val | p=0,1 | 4,03 ± 1,46 | 2,76× |
| val | p=0,2 | 8,19 ± 4,42 | 1,85× |
| test | p=0,1 | 4,17 ± 4,37 | 0,95× |
| test | p=0,2 | 4,67 ± 4,25 | 1,10× |

Yang boleh diklaim adalah **arah dan bentuk** kurva, bukan angka penurunan satu
kelompok tertentu. Delapan kelompok, delapan-duanya positif; uji tanda dua sisi
memberi p = 0,0078, tetapi kelompoknya berbagi data sehingga itu indikasi arah,
bukan uji formal.

Bentuk kurvanya: di **val**, 50 sampai 83 persen penurunan terjadi di langkah
terakhir saja, yaitu τ=0,8 ke τ=1,0. Degradasi termal parsial nyaris tidak
berbiaya; yang mahal hanya kehilangan total. Di **test** polanya tidak konsisten,
18 sampai 100 persen, jadi klaim "dataran lalu jurang" hanya untuk val.

---

## 5. Ablation #3: p tetap tidak dapat dibedakan

| partisi | rentang antar-p | simpangan khas | rasio | urutan terbaik ke terburuk |
|---|---|---|---|---|
| val | 4,16 | 2,93 | 1,42× | p=0,1 · p=0,3 · p=0,2 |
| test | 2,50 | 4,72 | 0,53× | p=0,1 · p=0,2 · p=0,3 |

**Urutannya berbeda antara val dan test.** Itu tanda khas peringkat yang
digerakkan derau. Pertahankan p = 0,2, dan katakan terus terang bahwa p tidak
dipilih berdasarkan hasil melainkan karena tidak ada pembeda yang lolos derau.

---

## 6. Rumusan yang boleh dan tidak boleh dipakai

**Boleh:**
- Kehilangan modalitas termal sepenuhnya berbiaya sekitar 5 poin akurasi pada
  partisi uji; degradasi parsial jauh lebih murah.
- Tidak ada satu pun kurva yang membalik, termasuk pada encoder yang sama dengan
  babak semifinal.
- Pembalikan di babak semifinal adalah artefak kriteria seleksi model, dan kami
  menunjukkan penyebabnya secara terkendali.
- Akurasi kondisi bersih pada partisi uji adalah 85 sampai 88 persen, bukan 98
  seperti angka validasi.

**Tidak boleh:**
- Menyebut satu nilai p lebih baik.
- Menyebut encoder termal baru lebih baik.
- Memakai angka validasi sebagai klaim performa.
- Menyebut kurvanya "monoton" tanpa menyebut tiga langkah naik kecil itu.
- Menyebut sistemnya kini lebih akurat. Akurasi kondisi bersih justru turun
  sekitar 1 poin. Yang meningkat adalah ketahanan dan keterulangan.
