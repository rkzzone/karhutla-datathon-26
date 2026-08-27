# Catatan Integrasi NASA FIRMS

**Untuk:** bagian Metodologi / Lampiran
**Status:** berfungsi, terverifikasi 9 Agustus 2026

---

## 1. Sumber data

**NASA FIRMS** (Fire Information for Resource Management System), produk deteksi
titik panas aktif dari citra satelit.

| Parameter | Nilai |
|---|---|
| Endpoint | `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SUMBER}/{AREA}/{HARI}` |
| Sumber default | `VIIRS_SNPP_NRT` |
| Format respons | CSV |
| Rentang waktu | 1 hari (dapat diatur 1–7) |
| Autentikasi | `MAP_KEY`, gratis, didaftarkan dengan alamat email |
| Kuota | 5.000 transaksi per 10 menit |

**VIIRS SNPP NRT** dipilih ketimbang MODIS: resolusi spasialnya 375 m
dibanding 1 km, sehingga titik panas berukuran kecil — yang justru khas pada
kebakaran gambut tahap awal — punya peluang lebih besar terdeteksi.

**NRT** (Near Real-Time) berarti data tersedia beberapa jam setelah lintasan
satelit, bukan seketika. Ini batas fisik produk, bukan batas implementasi kami.

---

## 2. Cakupan wilayah

Bounding box, dapat diatur lewat environment variable:

| Batas | Nilai | Env |
|---|---|---|
| Lintang selatan | −4.5° | `AOI_MIN_LAT` |
| Lintang utara | +1.5° | `AOI_MAX_LAT` |
| Bujur barat | 100.0° | `AOI_MIN_LON` |
| Bujur timur | 117.0° | `AOI_MAX_LON` |

Mencakup Sumatra bagian tengah–selatan dan Kalimantan — konsentrasi lahan
gambut terbesar di Indonesia (Riau, Jambi, Sumatera Selatan, Kalimantan
Tengah, Kalimantan Barat, Kalimantan Selatan).

**Tidak** mencakup Papua, Sulawesi, dan Jawa. Bukan karena tidak penting, tapi
karena AOI sengaja dipersempit ke wilayah yang jadi fokus proposal.

---

## 3. Arsitektur pemanggilan

```
Browser  ──►  Backend (proksi)  ──►  NASA FIRMS
              MAP_KEY di sini
```

Browser **tidak pernah** memanggil NASA langsung. Alasannya tunggal dan
menentukan: `MAP_KEY` harus tetap di server. Kalau key ditaruh di frontend, ia
akan ikut terpanggang ke bundle JavaScript dan bisa dibaca siapa pun lewat
devtools.

Backend juga menormalkan CSV FIRMS jadi JSON, sehingga frontend tidak perlu
mengurus perbedaan skema antar-sumber (MODIS memakai kolom `brightness`,
VIIRS memakai `bright_ti4`).

---

## 4. Pemrosesan

### 4.1 Normalisasi

| Keluar | Asal | Keterangan |
|---|---|---|
| `lat`, `lon` | `latitude`, `longitude` | Baris tanpa koordinat dibuang |
| `kecerahan_k` | `bright_ti4` \| `brightness` | Kelvin |
| `frp_mw` | `frp` | Fire Radiative Power, megawatt |
| `keyakinan` | `confidence` | `l`/`n`/`h` |
| `satelit` | `satellite` | |
| `waktu_akuisisi` | `acq_date` + `acq_time` | Digabung jadi ISO 8601 UTC |
| `siang_malam` | `daynight` | |

### 4.2 Pemangkasan

Pada puncak musim kemarau, AOI mengembalikan **>2.000 titik** (313 KB).
Merender sebanyak itu sebagai marker peta membuat tampilan tersendat dan —
lebih penting — **menenggelamkan alert model** di baliknya.

Respons dipangkas ke **400 titik dengan FRP tertinggi**. FRP dipilih sebagai
kriteria karena ia proksi intensitas radiatif kebakaran, sehingga yang
dipertahankan adalah yang paling relevan secara operasional.

Antarmuka menyebutkan pemangkasan ini secara eksplisit — *"400 terkuat dari
2467 terdeteksi"* — bukan diam-diam membuang sisanya. Jumlah total tetap
dilaporkan di field `jumlah_total`.

### 4.3 Cache

Dua lapis, TTL 5 menit:

| Lapis | Mekanisme | Alasan |
|---|---|---|
| Proses | dict in-memory | Instans hangat tidak memanggil NASA berulang |
| CDN | `Cache-Control: s-maxage=300, stale-while-revalidate=3600` | Lintas-instans, dan `stale-while-revalidate` menyajikan salinan terakhir yang berhasil saat NASA lambat/tumbang |

TTL 5 menit sangat konservatif terhadap laju pembaruan FIRMS NRT (beberapa jam
sekali) — tidak ada data yang terlewat.

**Efek terukur:** panggilan pertama 1,0–22,9 detik (tergantung latensi NASA),
panggilan berikutnya **0,14 detik**.

---

## 5. Tiga keadaan penyajian

Antarmuka membedakan ketiganya dan **tidak pernah menyamakannya**:

| Keadaan | Penanda visual | Arti |
|---|---|---|
| **Langsung** | Titik berdenyut | Ditarik dari NASA saat halaman dibuka |
| **Cuplikan** | Ikon jam + tanggal pengambilan | Hotspot nyata, dibekukan pada waktu tercatat |
| **Contoh** | Banner "berkas contoh" | Titik karangan; hanya muncul kalau cuplikan belum pernah dibuat |

Denyut sengaja tidak dipakai untuk cuplikan — denyut menandakan aliran
langsung, dan memakainya di sana akan menyiratkan kebaruan yang tidak dimiliki
cuplikan.

Keadaan **cuplikan** ada karena deployment statis tidak boleh membawa
`MAP_KEY`. Berkas cuplikan dihasilkan `backend/scripts/bekukan_firms.py`, yang
**menolak menulis** kalau yang diterima berupa fixture atau nol titik —
membekukan data karangan tidak ada gunanya.

---

## 6. Penanganan kegagalan

| Kondisi | Perilaku |
|---|---|
| `MAP_KEY` kosong | HTTP 503, `alasan: map_key_missing` |
| NASA tidak merespons / 4xx / 5xx | HTTP 503, `alasan: upstream_error` |
| Respons tidak bisa diparse | HTTP 503, `alasan: upstream_error` |

Pesan yang tampil ke operator, sesuai `DESIGN_BRIEF` Bagian 6:

> Data hotspot satelit tidak bisa dimuat. Coba lagi dalam beberapa menit, atau
> lanjutkan dengan sumber pemicu lain.

Peta **tetap dapat dipakai** saat FIRMS gagal — lapisan alert model, sensor,
dan rute patroli tidak terpengaruh. Kegagalan satu lapisan tidak melumpuhkan
halaman.

**URL NASA tidak pernah masuk log**, karena `MAP_KEY` ada di dalamnya. Yang
dicatat hanya tipe exception-nya.

---

## 7. Keterbatasan — sebutkan di paper

1. **Latensi NRT.** Data tersedia beberapa jam setelah lintasan satelit. Sistem
   ini **bukan** deteksi seketika dari satelit; FIRMS berperan sebagai pemicu
   penyaring wilayah, bukan alarm real-time.

2. **Resolusi 375 m.** Kebakaran gambut bawah permukaan dengan tanda panas
   permukaan kecil dapat lolos sepenuhnya. Justru inilah alasan sistem tidak
   bergantung pada FIRMS saja dan memadukan sensor darat serta patroli.

3. **Tergantung tutupan awan.** VIIRS optik; awan tebal memblokir deteksi.
   Musim kebakaran gambut Indonesia beririsan dengan periode berawan.

4. **Hotspot ≠ kebakaran.** FIRMS menandai anomali termal. Tungku industri,
   suar gas, dan pembakaran lahan terkendali ikut terdeteksi. Sistem ini
   memakainya sebagai **pemicu untuk diverifikasi**, bukan sebagai konfirmasi.

5. **Belum ada validasi silang** antara hotspot FIRMS dan keluaran model pada
   lokasi yang sama. Keduanya saat ini adalah lapisan terpisah di peta.

6. **AOI tetap.** Wilayah di luar bounding box tidak terpantau.

7. **Kuota bersama.** 5.000 transaksi / 10 menit berlaku per `MAP_KEY`. Cukup
   untuk demo; penempatan multi-posko perlu perhitungan ulang.

---

## 8. Verifikasi

Diuji 9 Agustus 2026 terhadap deployment produksi:

```
GET /api/firms/hotspots
  is_fixture  : false
  jumlah      : 400 (dari 2467 terdeteksi)
  FRP         : 15,1 – 128,9 MW
  cache MISS  : 1,03 detik
  cache HIT   : 0,14 detik
```

Reproduksi:

```bash
curl -s "https://<backend>/api/firms/hotspots" | python -m json.tool | head -20
```
