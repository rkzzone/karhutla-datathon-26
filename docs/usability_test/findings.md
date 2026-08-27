# Temuan Evaluasi Antarmuka & Iterasi yang Dihasilkannya

**Produk:** Konsol Operator Deteksi Dini Karhutla Gambut
**Periode:** 3–9 Agustus 2026 · 19 putaran evaluasi
**Penyusun:** tim produk (produk)

---

## ⚠️ Baca ini sebelum mengutip dokumen ini di paper

**Yang dilaporkan di sini BUKAN uji pengguna (usability testing).** Tidak ada
partisipan manusia yang dilibatkan. Menyebutnya "hasil uji pengguna" di paper
akan menjadi klaim palsu.

Metode yang benar-benar dipakai, dan istilah yang boleh dipakai di paper:

| Metode | Keterangan |
|---|---|
| **Evaluasi heuristik** | Penilaian ahli terhadap antarmuka dibandingkan spesifikasi desain (`DESIGN_BRIEF.md`) dan wireframe, 19 putaran terdokumentasi |
| **Audit aksesibilitas terinstrumentasi** | Rasio kontras WCAG dan simulasi buta warna dihitung secara terprogram, bukan dinilai dengan mata |
| **Uji lintas-keadaan** | Setiap halaman diperiksa pada keadaan data normal, `null`, kosong, dan galat |

Evaluasi heuristik adalah metode yang sah dan bisa disitasi (Nielsen &
Molich, 1990) — tapi ia **melengkapi**, bukan menggantikan, uji dengan pengguna
nyata. Rubrik 1c kemungkinan besar menuntut yang kedua.

**Protokol siap-jalan untuk menutup kekurangan ini ada di Bagian 4.** Perlu
~2 jam dan 3–5 partisipan.

---

## 1. Ringkasan

19 putaran evaluasi menghasilkan **10 temuan** yang seluruhnya menyebabkan
perubahan antarmuka. Empat di antaranya adalah cacat yang akan lolos ke
pengguna kalau hanya mengandalkan penilaian visual sekilas — ketiganya
ditemukan lewat pengukuran, bukan lewat "kelihatannya kurang pas".

Jejak lengkap tiap putaran disimpan bersama tangkapan layar kerja, di luar repositori ini.

---

## 2. Temuan dan iterasi yang dihasilkannya

### T-01 — Tiga warna skala risiko gagal ambang kontras teks

**Metode:** perhitungan rasio kontras WCAG terhadap permukaan kartu.

**Temuan:** tiga dari enam warna yang dipakai untuk teks tingkat risiko berada
di bawah ambang AA 4.5:1 di atas `ash-900`:

| Token | Rasio | Status |
|---|---|---|
| `smoke` #6B6259 | 2.93:1 | gagal |
| `ember` #C1392B | 3.24:1 | gagal |
| `canopy-400` #4A7A5E | 3.53:1 | gagal |
| `haze-400` #B8AFA0 | 8.07:1 | lolos |

Operator membaca tingkat risiko dalam kondisi terburu-buru; teks yang samar
pada label "Risiko kritis" adalah kegagalan fungsional, bukan estetika.

**Iterasi:** setiap tingkat risiko dipecah jadi dua nilai — `isi` (untuk
fill/marker/ribbon) dan `teks` (satu-satunya yang boleh jadi teks). Ketiga
warna di atas dikunci hanya untuk `isi`. Diterapkan di `frontend/src/lib/risk.js`.

**Efek samping yang berguna:** saat tema terang ditambahkan, arah kegagalan
berbalik — `flare` jatuh ke 1.56:1 dan `flame` ke 2.83:1 di atas kertas.
Pemisahan `isi`/`teks` yang sudah ada membuat penanganannya cuma mengganti
nilai variabel, bukan membongkar komponen.

---

### T-02 — Selisih keyakinan tidak terbaca pada ribbon

**Metode:** evaluasi heuristik terhadap wireframe (`DESIGN_BRIEF` Bagian 3).

**Temuan:** ribbon Ironbow di tepi kartu seharusnya menyandikan keyakinan lewat
tebal dan tinggi isian. Pada rentang 4–10 px, kartu 94% dan 87% praktis
tidak terbedakan — padahal justru selisih itu yang dipakai operator untuk
memilih mana yang dikejar duluan.

**Iterasi:** rentang tebal dinaikkan (4→10 px) dan ditambahkan **takik** garis
gelap tepat di batas isian, sehingga posisi isian punya tepi yang tegas, bukan
gradien yang meluruh.

**Verifikasi:** run 05 — perbedaan terbaca dari jarak pandang normal.

---

### T-03 — Peta menampilkan separuh Asia Tenggara

**Temuan:** zoom statis level 5 membuat seluruh marker mengecil jadi debu.
Peta adalah elemen utama Halaman 1; menampilkannya "cantik dari luar angkasa"
membuatnya tidak berguna secara operasional.

**Iterasi:** `fitBounds` otomatis ke bounding box data aktual saat muat pertama,
dengan `maxZoom` 8 supaya tidak melompat terlalu dekat saat titiknya sedikit.

---

### T-04 — Marker sensor melanggar semantik warna sistem

**Temuan:** marker IoT sempat diwarnai mengikuti skala Ember menurut status
sensor (kritis→oranye, waspada→kuning). Ini menabrak aturan inti sistem: skala
Ember adalah milik **skor risiko model**, sedangkan mauve menandakan **sumber
pemicu**. Akibatnya bacaan sensor simulasi terlihat setara keputusan model.

**Iterasi:** marker IoT dikembalikan ke mauve permanen; status di-encode lewat
**bentuk** — ketebalan cincin luar dan denyut — bukan lewat hue.

**Catatan proses:** cacat ini diperkenalkan oleh evaluator sendiri pada run 02
dan tertangkap pada run 03. Ia dicatat apa adanya karena menunjukkan bahwa
putaran evaluasi berulang memang menangkap regresi, bukan cuma memoles.

---

### T-05 — Pita hitam pada bingkai citra (tiga iterasi)

**Temuan awal (run 01):** `object-contain` menyisakan pita hitam di kiri-kanan
citra RGB dan termal. Panel terlihat rusak, bukan seperti umpan kamera.

**Iterasi 1 (run 02):** ganti ke rasio tetap + `object-cover`.
**Iterasi 2 (run 03):** ternyata `aspect-*` + `max-h` justru **menyusutkan
lebar** demi menjaga rasio — pita kosong pindah, tidak hilang.
**Iterasi 3 (run 04):** tinggi tetap (`h-[288px]`) + `object-cover`. Selesai.

Dicatat sebagai tiga iterasi karena memang butuh tiga; perbaikan pertama
menghasilkan gejala baru yang hanya terlihat lewat tangkapan layar berikutnya.

---

### T-06 — Heatmap menutupi seluruh bingkai

**Metode:** inspeksi distribusi keluaran model, bukan penilaian visual.

**Temuan:** overlay lokalisasi menutupi hampir seluruh citra. Penyebabnya bukan
bug render: median sigmoid keluaran `segmentation_head` ada di ~0.69, sehingga
mayoritas piksel memang bernilai tinggi. Overlay yang menutupi segalanya tidak
menunjukkan apa pun.

**Iterasi:** ambang persentil-90 diterapkan sebelum render, mengikuti config
Stage 6 tim model. Piksel di bawah ambang jadi transparan penuh.

**Efek sampingan:** berkas heatmap menyusut drastis (7 berkas total 408 KB),
karena mayoritas piksel jadi transparan dan terkompresi baik.

---

### T-07 — Label sumber data berbohong setelah Stage 10

**Temuan:** header menampilkan `sumber mock` padahal seluruh angka sudah
keluaran `fusion_v3_localization.pth`. Di depan juri, ini meremehkan pekerjaan
sendiri; kebalikannya (menampilkan "model" untuk data karangan) akan menipu.

**Iterasi:** penanda sumber dipecah jadi **tiga keadaan** — `mock` (data
karangan), `batch` (keluaran model, dihitung sekali), `model_service` (layanan
hidup). Ditulis otomatis oleh skrip inference, sehingga tidak bisa tertinggal
basi.

---

### T-08 — Galat runtime bocor ke layar operator

**Temuan:** salah konfigurasi alamat layanan membuat server membalas HTML
dengan status 200. Frontend menganggapnya sukses, lalu parser JSON melempar
`Unexpected token '<', "<!doctype "... is not valid JSON` **langsung ke layar
operator**. `DESIGN_BRIEF` Bagian 6 mewajibkan copy fungsional berbahasa
Indonesia; galat runtime jelas melanggarnya.

**Iterasi:** dua perbaikan —
1. Pengaman parsing: status 200 dengan badan non-JSON kini menghasilkan pesan
   *"Alamat layanan membalas halaman web, bukan data."* dengan kode teknis
   tetap tampil di baris `kode:` untuk yang memperbaiki.
2. Aturan rewrite `/api/*` dikembalikan, supaya salah alamat menghasilkan 404
   yang jujur alih-alih 200 yang menyesatkan.

---

### T-09 — Palet grafik gagal simulasi buta warna

**Metode:** simulasi protanopia/deuteranopia/tritanopia dengan perhitungan ΔE
untuk **semua pasangan** seri, bukan hanya yang bersebelahan.

**Temuan:** di tema terang, kombinasi hijau-tua vs merah-tua menghasilkan
**ΔE 4.3 untuk protanopia** — praktis satu warna bagi pembaca buta warna merah.

**Iterasi:** seri `rgb_only` di tema terang diganti ke satellite-blue.
Penyimpangan dari "seri pakai skala Ember" ini disengaja dan dicatat, karena
`DESIGN_BRIEF` Bagian 5 menyatakan aksesibilitas wajib, bukan opsional.
Tambahan: identitas seri tidak pernah bergantung warna saja — ada pola garis
dan label langsung di ujung garis.

---

### T-10 — 2.016 marker menenggelamkan alert model

**Temuan:** pada puncak musim kemarau, AOI Sumatra–Kalimantan mengembalikan
2.016 hotspot FIRMS (313 KB). Merender semuanya membuat peta tersendat dan —
lebih buruk — **menyembunyikan alert model di baliknya**.

**Iterasi:** dipangkas ke 400 titik ber-FRP tertinggi. UI menyebut angkanya
apa adanya: *"400 terkuat dari 2016 terdeteksi"*, bukan diam-diam membuang.

---

## 3. Ringkasan iterasi

| # | Temuan | Iterasi | Bukti |
|---|---|---|---|
| T-01 | Kontras teks gagal AA | Pisah `isi`/`teks` | Rasio terhitung |
| T-02 | Ribbon tak terbaca | Tebal 4–10px + takik | run 01→05 |
| T-03 | Zoom peta statis | `fitBounds` ke data | run 01→02 |
| T-04 | Marker IoT langgar semantik | Bentuk, bukan hue | run 02→03 |
| T-05 | Pita hitam citra | 3 iterasi → tinggi tetap | run 01→04 |
| T-06 | Heatmap menutupi bingkai | Ambang persentil-90 | run 13 |
| T-07 | Label sumber berbohong | Tiga keadaan sumber | Stage 10 |
| T-08 | Galat parser bocor | Pengaman + rewrite 404 | Reproduksi |
| T-09 | Palet gagal CVD | Ganti seri tema terang | ΔE terhitung |
| T-10 | Marker menenggelamkan alert | Pangkas 400 + label jujur | Stage 11 |

Rubrik meminta minimal 2 iterasi; terdokumentasi **10**.

---

## 4. Protokol uji pengguna — belum dijalankan

Bagian ini **belum menghasilkan data**. Ditulis supaya bisa dijalankan cepat
sebelum submission. Perkiraan waktu: 2 jam total.

### Partisipan

3–5 orang. Prioritas, urut dari paling relevan:
1. Petugas Manggala Agni / BPBD (target sesungguhnya)
2. Mahasiswa kehutanan / geografi
3. Siapa pun yang belum pernah melihat produk ini

3 partisipan sudah cukup menemukan mayoritas masalah besar; jangan tunda demi
jumlah.

### Tugas (jangan beri petunjuk cara mengerjakannya)

| # | Tugas | Yang diukur |
|---|---|---|
| 1 | "Dari semua yang tampil, mana yang harus ditangani lebih dulu? Kenapa?" | Apakah hierarki risiko terbaca |
| 2 | "Menurut Anda seberapa yakin sistem pada alert itu, dan atas dasar apa?" | Apakah badge modalitas dipahami |
| 3 | "Tandai alert ini sebagai alarm palsu." | Ketemuannya tombol keputusan |
| 4 | "Mana titik yang datang dari satelit, mana dari sensor?" | Apakah warna sumber terbaca |
| 5 | "Apa arti tampilan ini?" (buka alert `modality_reliability: null`) | Apakah keadaan kosong dipahami jujur |

### Yang dicatat

- Waktu penyelesaian per tugas
- Jumlah salah klik sebelum berhasil
- **Kutipan verbatim** saat partisipan ragu atau salah paham
- Tugas yang gagal diselesaikan tanpa bantuan

### Aturan

Jangan membela desain saat partisipan bingung. Kebingungan itu **datanya**.
Catat, lanjut.

### Sesudahnya

Isi tabel di bawah, lakukan minimal 2 perubahan UI karenanya, catat di
log putaran sebagai run baru, lalu perbarui dokumen ini.

| Partisipan | Tugas gagal/ragu | Kutipan | Perubahan yang dilakukan |
|---|---|---|---|
| P1 | | | |
| P2 | | | |
| P3 | | | |

---

## 5. Keterbatasan yang harus disebut di paper

1. **Belum ada uji dengan pengguna nyata.** Seluruh temuan di atas berasal dari
   evaluasi ahli dan audit terinstrumentasi.
2. **Evaluator adalah pembangun produknya sendiri**, sehingga rentan buta
   terhadap asumsi sendiri — T-04 adalah contoh nyata cacat yang diperkenalkan
   lalu ditemukan sendiri, tapi tidak ada jaminan semua tertangkap.
3. **Belum diuji pada perangkat keras posko sesungguhnya** maupun kondisi
   jaringan lapangan.
4. **Belum diuji dengan operator dalam kondisi tertekan waktu**, padahal itu
   justru konteks pemakaian yang dirancang.
