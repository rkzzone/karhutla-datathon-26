# Temuan RUN 2B — tolok ukur bersih itu jenuh, dan itu membatalkan dua kesimpulan

RUN 2B adalah run pertama yang memakai benih terkunci (P8). Ia berhasil pada
tujuannya, dan justru karena berhasil, ia memperlihatkan masalah yang lebih besar
daripada yang hendak diperbaikinya.

Angka di halaman ini dipulihkan dari log run, bukan dari berkas CSV. Alasannya
ada di bagian terakhir.

---

## 1. Yang gugur

### Klaim A/B encoder termal

Setelah RUN 2 satu benih, saya menulis bahwa encoder termal baru menaikkan
akurasi termal-saja sebesar **+44,6 poin**, dan bahwa selisih itu "hampir pasti
nyata" karena derau antar-run yang teramati sekitar 5 poin. Kedua bagian
pernyataan itu salah.

| encoder termal | termal-saja, tiga benih | rerata | simpangan |
|---|---|---|---|
| LAMA, val Stage 1 = 0,5148 | 96,25 · 55,83 · 95,00 | **82,36** | 22,98 |
| BARU, val Stage 1 = 0,9758 | 51,25 · 91,67 · 48,33 | **63,75** | 24,22 |

Selisihnya **-18,61 poin**, yaitu berlawanan arah dengan klaim, dengan simpangan
gabungan 23,61 poin. Rasio selisih terhadap derau 0,79. Tidak ada beda yang dapat
diklaim ke arah mana pun.

Estimasi derau saya sebesar 5 poin berasal dari dua run, dan hanya dari kolom
fusi dan RGB. Dua titik bukan penduga simpangan. Kolom yang menjadi tumpuan
klaim, yaitu termal-saja, ternyata berderau empat kali lebih besar.

### Sapuan p

| p | fusi | RGB saja | termal saja |
|---|---|---|---|
| 0,1 | 99,44 ± 0,96 | 90,55 ± 13,47 | 90,69 ± 4,73 |
| 0,2 | 100,00 ± 0,00 | 98,89 ± 0,96 | 63,75 ± 24,22 |
| 0,3 | 99,58 ± 0,42 | 96,39 ± 3,37 | 83,61 ± 17,35 |

Selisih antar-p jauh lebih kecil daripada simpangan antar-benih. Ablation #3
tidak dapat disimpulkan dari akurasi kondisi bersih.

---

## 2. Kenapa, dan ini bagian yang berguna

Sebarannya sangat tidak merata antar-mode. Dua belas run digabung:

| mode | rentang | lebar | simpangan |
|---|---|---|---|
| fusi | 98,33 sampai 100,00 | 1,67 poin | **0,65** |
| RGB saja | 75,00 sampai 100,00 | 25,00 poin | 6,86 |
| termal saja | 48,33 sampai 97,50 | **49,17 poin** | **19,23** |

Kriteria seleksi checkpoint adalah akurasi fusi bersih di `rffnet_val`. Ukuran
itu **jenuh**: simpangannya 0,65 poin, dan di dalam satu run banyak epoch
berimpit tepat di 1,0000. Ketika banyak epoch seri, epoch mana yang tersimpan
praktis acak terhadap segala hal yang tidak ikut diukur. Yang tidak ikut diukur
adalah jalur unimodal, dan jalur unimodal itulah tumpuan seluruh klaim ketahanan.

Ini bukan ketidakstabilan pelatihan. Fusi stabil sampai 0,65 poin. Yang tidak
stabil adalah **pilihan epoch**, pada kuantitas yang tidak pernah masuk kriteria.

Rumusan yang lebih tajam: melatih dengan modality dropout, lalu memilih model
berdasarkan akurasi kondisi bersih, adalah memilih dengan ukuran yang bukan
tujuannya. Cacatnya bersifat metodologis, bukan sekadar derau.

---

## 3. Temuan kedua: Stage 1 hampir tidak menentukan

`train.py` baris 283 memasukkan `list(thermal_encoder.parameters())` ke
optimizer Stage 2. Seluruh encoder termal dilatih ulang di RFFNet.

Karena itu encoder yang hanya mencapai 0,5148 di validasi Stage 1 tetap bisa
menghasilkan termal-saja 96,25 sesudah Stage 2. Bobot Stage 1 adalah titik awal
yang sebagian besar ditimpa, bukan penentu.

Konsekuensinya untuk narasi: perbaikan RUN 1, yaitu P5 batas video, P6 split
berblok, dan P7 pemilihan checkpoint, tetap **benar dan wajib** karena `val_acc`
Stage 1 yang lama memang tidak dapat ditafsirkan. Tetapi dampak hilirnya kecil,
dan **jangan** dibingkai sebagai sumber perbaikan performa.

---

## 4. Berkas p = 0,2 encoder BARU hilang dari disk

P8 memberi sufiks benih, sehingga tabrakan antar-benih hilang. Identitas encoder
tidak ikut ke nama berkas, sehingga tabrakan **antar-encoder** tetap ada. Sel A/B
menjalankan encoder LAMA dengan nama keluaran yang sama persis, menimpanya lebih
dulu, lalu mengganti nama menjadi `_ENCLAMA` sesudahnya. Sembilan berkas p=0,2
encoder BARU, tiga checkpoint dan tiga CSV, hilang.

Angka-angkanya masih ada di log, dan sudah dipulihkan ke
[`ablation1_run2b_PULIH.csv`](ablation1_run2b_PULIH.csv) oleh
[`pulihkan_dari_log.py`](pulihkan_dari_log.py).

Ditutup oleh **P10**, yaitu argumen `--tag`.

---

## 5. Yang dikerjakan sesudah ini

| Patch | Isi |
|---|---|
| **P9** | Kriteria seleksi checkpoint menjadi rerata akurasi tiga mode ketersediaan modalitas |
| **P10** | Argumen `--tag`, mencegah tabrakan antar-encoder |

Dijalankan lewat `runs/02b_seleksi_diperbaiki.py`, yang sekaligus
menyerap RUN 3 ke sesi yang sama.

Disiplin baru yang berlaku sejak sekarang: **seleksi memakai val, pelaporan
memakai test.** Sesudah P9, angka val ikut dioptimasi oleh kriteria seleksi,
jadi ia tidak boleh menjadi angka utama di slide.

---

## 6. Nilai temuan ini untuk babak final

Jangan buang temuan ini hanya karena ia berupa koreksi atas diri sendiri. Ia
menjelaskan tiga hal yang sebelumnya menggantung:

1. **Kenapa hasil semifinal tidak stabil dan kurva degradasinya membalik.**
   Checkpoint dipilih dengan ukuran jenuh, jadi jalur unimodal setiap run adalah
   undian. Kurva yang membalik adalah gejala yang diperkirakan dari mekanisme
   ini, bukan sifat arsitektur fusi.
2. **Kenapa tolok ukur kondisi bersih tidak layak menjadi metrik utama.** Ini
   memperkuat, bukan melemahkan, alasan keberadaan protokol kurva degradasi yang
   memang menjadi kontribusi yang diklaim.
3. **Kenapa hasil satu benih tidak boleh dipercaya.** Ada angkanya sekarang,
   bukan sekadar anjuran metodologis.

Yang tidak boleh dilakukan: melaporkan +44,6 poin, atau menyebut satu nilai p
lebih baik, atau menyebut encoder termal baru terbukti lebih baik.
