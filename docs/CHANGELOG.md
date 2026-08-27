# Riwayat perubahan

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/).

## [0.9.0] — 2026-08-27

Versi yang disiapkan untuk demonstrasi final.

### Ditambahkan

- **Lapisan size-up** — konteks keputusan setelah deteksi: cuaca titik
  (Open-Meteo), indeks bahaya kebakaran FWI, prakiraan resmi BMKG, batas wilayah
  dan penutup lahan (BIG), sumber air dan akses jalan (OpenStreetMap), saran
  tingkat peralatan, serta brief siap tempel ke grup siaga.
- **Rantai alur per alert** — pemicu → verifikasi udara → klasifikasi model →
  keputusan operator → pengerahan tim, dengan status waktu tiap tahap.
- **Prioritas verifikasi** — urutan kunjungan titik curiga di bawah kendala daya
  tahan wahana, diselesaikan sebagai *orienteering problem* dengan aturan
  deterministik.
- Proyeksi arah angin, rute pengerahan regu darat mengikuti jaringan jalan, dan
  lapisan sumber air/akses per titik pada peta operasi.
- Endpoint `GET /api/sizeup`, terpisah dari skema alert sehingga kontrak API
  tidak berubah.

### Diubah

- Indeks bahaya kebakaran beralih dari aturan ambang internal ke **Sistem FWI
  Kanada** (van Wagner, 1987), dihitung dari 60 hari riwayat cuaca titik.
- Basemap beralih dari Esri Canvas ke **CARTO Dark Matter** saat kunci tersedia;
  Esri tetap menjadi cadangan otomatis sehingga repositori berjalan tanpa kunci.
- Data demo dipusatkan pada satu wilayah operasi yang koheren, dengan posisi
  alert diturunkan dari rantai alur alih-alih ditebar bebas.
- Penomoran skrip pelatihan dibuat berurutan tanpa celah.

### Diperbaiki

- Angka evaluasi dihitung ulang setelah audit label; hasil yang lebih rendah
  dipertahankan dan yang lama dibuang.
- Rute pengerahan darat kini menolak menyajikan rute yang titik ujungnya
  ditempelkan terlalu jauh ke jaringan jalan, dan menyatakan ketiadaan akses apa
  adanya.
- Kegagalan sumber data luar dilaporkan per blok, tanpa menambal blok kosong
  dengan nilai tebakan.

### Catatan

Nilai yang belum terukur dirender sebagai `—`, tidak pernah sebagai nol. Data
yang dibekukan diberi label beserta waktu perekamannya. Keterbatasan yang
diketahui didaftarkan pada README akar.
