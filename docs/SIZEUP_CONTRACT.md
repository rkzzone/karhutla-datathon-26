# SIZEUP_CONTRACT.md — lapisan size-up, di luar skema alert


## Kenapa berkas ini terpisah dari `API_CONTRACT.md`

`API_CONTRACT.md` wajib identik byte-per-byte dengan salinan tim model dan mengunci bentuk objek alert. Lapisan size-up:

- **tidak menambah satu field pun** ke objek alert,
- **tidak dihasilkan maupun dikonsumsi** oleh tim model,
- berjalan di endpoint sendiri (`GET /api/sizeup`).

Karena itu `API_CONTRACT.md` tidak disentuh dan tidak perlu disinkronkan ulang sehari sebelum pembekuan. Pagar "frontend tidak boleh menambah field di luar kontrak" tetap berlaku penuh untuk objek alert; berkas ini adalah kontrak untuk objek yang **berbeda**.

## Batas arsitektur yang dijaga

```
PEMICU              DETEKSI                    SIZE-UP                 TINDAKAN
FIRMS / sensor  →   fusi RGB+termal        →   konteks & rencana   →   keputusan operator
laporan warga       keandalan modalitas        cuaca, angin, air       brief ke grup siaga
                    lokalisasi                 akses, tingkat alat
                    ──────────────────         ──────────────────
                    MODEL TERLATIH             ATURAN DETERMINISTIK
                    (tidak berubah)            (dapat diaudit)
```

Aliran data **satu arah**: model → size-up. Cuaca tidak pernah menjadi masukan model deteksi (larangan nomor 13). Kalau suatu saat ada modul di jalur inference yang mengimpor `services/cuaca_client.py`, itu bug arsitektur.

## Endpoint

```
GET /api/sizeup?lat={float}&lon={float}&alert_id={string, opsional}
```

**Selalu 200, tidak pernah 503.** Berbeda dari `/api/firms/hotspots`: di sana kegagalan berarti seluruh lapisan hilang. Di sini kartu terdiri dari blok independen — cuaca tetap berguna walau Overpass tumbang. Kegagalan dilaporkan per blok lewat `blok.<nama>.status`.

## Bentuk respons

```json
{
  "koordinat": {"lat": -2.7148, "lon": 114.2213},
  "alert_id": "string ATAU null jika alert_id tidak dikirim/tidak dikenali",
  "diambil": "ISO 8601 dengan timezone eksplisit",
  "is_cuplikan": false,
  "blok": {
    "cuaca":         {"status": "ada | gagal", "...": "Open-Meteo, presisi titik"},
    "bahaya":        {"status": "ada | gagal", "...": "FWI, dihitung sendiri"},
    "wilayah":       {"status": "ada | gagal", "...": "BIG, batas desa + kode"},
    "bmkg":          {"status": "ada | gagal", "...": "prakiraan resmi, per desa"},
    "penutup_lahan": {"status": "ada | gagal", "...": "BIG 1:250.000"},
    "sumber_air":    {"status": "ada | gagal", "...": "OpenStreetMap"},
    "akses":         {"status": "ada | gagal", "...": "OpenStreetMap"},
    "peralatan":     {"status": "ada | gagal", "...": "aturan dari keterangan praktisi"}
  },
  "brief": "string — teks siap tempel ke grup siaga",
  "catatan_provenans": "string",
  "catatan_brief": "string"
}
```

Blok dengan `status: "gagal"` berisi `{"status", "alasan", "pesan"}` dan **tidak ada field numerik apa pun**. Ini pagar keras: blok gagal tidak pernah ditambal angka tebakan.

### `blok.cuaca` — sumber D1

| Field | Isi |
|---|---|
| `sumber`, `sumber_url` | `"Open-Meteo"`, tanpa kunci API |
| `waktu_pengamatan`, `zona_waktu` | waktu pengamatan apa adanya dari sumber |
| `suhu_c`, `kelembapan_persen`, `hujan_mm`, `angin_kmj` | nilai terukur |
| `arah_angin_deg`, `arah_angin_mata` | arah angin **datang** (konvensi meteorologi) |
| `arah_rambatan_deg`, `arah_rambatan_mata` | arah dorongan = arah datang + 180° |
| `riwayat_hujan.hari_kering_berturut` | hari berturut < `ambang_hari_kering_mm` (1,0 mm) |
| `riwayat_hujan.terpotong_jendela` | `true` = seluruh jendela kering → UI **wajib** render "≥ N hari" |
| `riwayat_hujan.harian` | hujan harian 7 hari terakhir |

Dua field arah dipisah dengan sengaja. Membaca yang satu sebagai yang lain akan membalik kerucut proyeksi 180°.

### `blok.bahaya` — Sistem FWI Kanada

| Field | Isi |
|---|---|
| `sistem` | `"Fire Weather Index (FWI) — Sistem Kanada, van Wagner 1987"` |
| `fwi` | nilai akhir |
| `tingkat`, `nama`, `ambang` | 1–4, `"Rendah"` … `"Ekstrem"`, plus ambang yang dipakai |
| `komponen` | `ffmc`, `dmc`, `dc`, `isi`, `bui` — enam kode antara |
| `hari_dipakai`, `nilai_awal`, `penyesuaian_ekuator` | parameter spin-up |
| `catatan`, `catatan_spinup` | keterbatasan, dikirim bersama angkanya |

Dihitung sendiri dari persamaan terbit, bukan ditarik dari mana pun. Portal SPBK BMKG (SPARTAN) adalah aplikasi ber-login tanpa API publik.

**Yang boleh dikatakan:** "kami menghitung FWI, sistem yang sama yang diadopsi SPBK BMKG."
**Yang tidak boleh:** "ini angka SPBK BMKG." Angka ini bukan keluaran BMKG, dan masukannya reanalisis Open-Meteo, bukan pengamatan stasiun BMKG.

Tiga keterbatasan dikirim di dalam payload — bukan disimpan di dokumentasi kode — supaya UI **tidak bisa** menampilkan angkanya tanpa batasnya:

1. **Faktor panjang hari.** Tabel Le/Lf asli disusun untuk 46°N. Dipakai penyesuaian ekuatorial Le 9.0, Lf 1.4 sepanjang tahun.
2. **Spin-up 60 hari dari nilai awal standar** (FFMC 85, DMC 6, DC 15). FFMC dan DMC konvergen; **DC bermemori ~50 hari sehingga masih menyimpan sebagian pengaruh nilai awal** — dan DC ikut menentukan BUI serta FWI.
3. **Masukan reanalisis**, bukan pengamatan stasiun.

UI tidak boleh menyembunyikan `komponen`: DC tinggi dengan FFMC rendah menceritakan situasi yang sama sekali berbeda dari kebalikannya, dan di gambut DC-lah yang paling berarti.

### `blok.wilayah` + `blok.bmkg` — rantai resmi Indonesia

BMKG **tidak menerima lintang/bujur**, hanya kode wilayah tingkat desa (`adm4`). Rantainya:

```
koordinat → BIG (batas desa) → KDEPUM → BMKG (prakiraan resmi desa itu)
```

`blok.wilayah` membawa `kode_desa`, `desa`, `kecamatan`, `kabupaten`, `provinsi`.
`blok.bmkg` membawa `suhu_c`, `kelembapan_persen`, `angin_kmj`, `arah_angin_deg`, `hujan_mm`, `cuaca`, `waktu_prakiraan`, dan **`jarak_titik_acuan_km`**.

**`jarak_titik_acuan_km` WAJIB dirender.** Prakiraan BMKG berlaku untuk desa, bukan untuk titik alert; pada contoh yang diuji selisihnya 3,73 km. Tanpa angka itu, dua tempat berbeda terbaca sebagai satu.

Rencana mengusulkan BMKG sebagai sumber **utama** dengan Open-Meteo sebagai cadangan. Setelah endpoint-nya diuji, susunannya dibalik, dan alasannya teknis: FWI menuntut nilai pada TITIK pada jam tertentu plus riwayat 60 hari, sedangkan BMKG publik memberi prakiraan ke depan untuk desa. Jadi **Open-Meteo menggerakkan angka, BMKG menampilkan prakiraan resmi** — berdampingan, masing-masing berlabel.

### `blok.penutup_lahan` — BIG, dan kenapa ini BUKAN peta gambut

`kode`, `nama`, `sni`, `skala`, `indikasi_lahan_basah`.

Yang dicari adalah Peta Lahan Gambut / KHG / Fungsi Ekosistem Gambut.

Yang ditemukan setelah menyapu server publik BIG secara menyeluruh (26 Agustus 2026): **78 layanan, 982 layer diperiksa satu per satu — nol layer gambut atau KHG.** Penyaringan memakai pola `gambut|peat|khg|hidrologis|rawa`; satu-satunya yang cocok adalah "Rawan Tsunami", "Rawan Gempa Bumi", dan "Rawan Gerakan Tanah" — kata **"rawan"**, bukan "rawa". Host gambut lain yang dicoba (`sigap.menlhk.go.id`, `geoportal.menlhk.go.id`, `geoportal.brgm.go.id`) tidak ada dalam DNS; `portal.ina-sdi.or.id` gagal TLS.

Angka 78/982 di atas berasal dari **enumerasi lengkap terpisah** (nol bagian terlewat). Tiga sapuan skrip pada hari yang sama, masing-masing bolong sedikit (76/944, 78/967, 67/867), semuanya juga menemukan nol layer gambut. Empat pengamatan sepakat.

**Klaim negatif ini bisa diperiksa ulang siapa pun:** `python backend/scripts/sapu_layer_big.py`. Skrip itu melacak bagian yang gagal dibaca dan **menolak menyimpulkan "tidak ada" kalau sapuannya bolong** — nol temuan pada sapuan tidak lengkap bukan bukti ketiadaan.

**BIG membatasi laju.** Setelah beberapa sapuan penuh beruntun ia berhenti menjawab sama sekali; blokirnya sementara. Jalankan sekali, bukan berulang. Kalau BIG kelak menerbitkan layer gambut, skrip itu yang akan menemukannya lebih dulu, dan blok ini harus segera diperbarui.

Karena itu yang disajikan adalah **penutup lahan** — pertanyaan size-up yang nyata dan berbeda ("api ini di perkebunan, hutan rimba, atau permukiman?"). `indikasi_lahan_basah` menyalakan catatan **indikasi**, tidak pernah penetapan: status KHG adalah dokumen hukum dan tidak boleh disimpulkan dari peta penutup lahan. Alasan ini ditampilkan **di layar**, bukan cuma di berkas ini — kalau juri bertanya "kenapa tidak pakai peta KHG", jawabannya sudah ada di depan mereka.

### `blok.sumber_air` / `blok.akses` — sumber D4

`daftar` berisi maksimal 6 fitur terurut jarak menaik. Tiap fitur: `jenis`, `jenis_nama`, `nama` (boleh `null`), `jarak_km`, `arah_deg`, `lat`, `lon`. Air punya `kanal_gambut` (bool); akses punya `kendaraan_berat` (bool — `track`/`service` tidak dihitung memadai untuk alat mekanis).

`jarak_km` diukur ke **simpul terdekat** pada jalur, bukan ke titik tengahnya. Pencarian berjenjang 2 → 5 → 12 km. `daftar` kosong dengan `status: "ada"` berarti benar-benar tidak ada yang terpetakan dalam radius itu — bukan kegagalan.

### `blok.peralatan`

`tingkat` ∈ `manual | semi_mekanis | mekanis`, dengan `nama`, `contoh`, `alasan` (daftar kalimat berisi jarak yang memicunya), dan `catatan`. Kosakata tingkatan berasal dari keterangan praktisi polisi hutan. Ini **saran**, bukan perintah.

## Aturan pelabelan UI — tidak boleh dilanggar

Rancangan Bagian 4, dan konsisten dengan disiplin provenans yang sudah berjalan di produk:

1. Cuaca dan data OSM **nyata**, ditarik untuk **koordinat yang penempatannya simulasi**. Kedua fakta dinyatakan berdampingan, jangan salah satunya saja.
2. Kerucut arah diberi label **"proyeksi arah angin"**, tidak pernah "prediksi model" atau "prediksi rambatan".
3. Brief diberi label **"draf untuk verifikasi tim size-up"**. Sistem tidak pernah menyatakan api padam dan tidak pernah menentukan arah serangan.
4. Blok bahaya disebut apa adanya sebagai **aturan ambang internal**, bukan indeks terbit dan bukan keluaran AI.

## Tiga keadaan sumber (frontend)

Sama persis dengan lapisan FIRMS — jangan disamakan satu sama lain:

| Keadaan | Artinya | Dari mana |
|---|---|---|
| `langsung` | ditarik saat panel dibuka | `VITE_LIVE_BASE` terisi |
| `cuplikan` | cuaca & geografi nyata, beku pada waktu tercatat | `/mock/sizeup_snapshot.json` |
| tidak tersedia | tidak ada backend dan belum pernah dibekukan | keduanya kosong |

Cuplikan dihasilkan `backend/scripts/bekukan_sizeup.py`. **Jangan merekam demo dengan mengandalkan Overpass hidup** — lihat catatan blokir di kepala skrip itu.

## Berkas pendamping — di luar objek size-up

Tiga berkas statis dihasilkan skrip dan dikonsumsi peta. Tak satu pun menyentuh objek alert, jadi `API_CONTRACT.md` tetap tidak tersentuh.

| Berkas | Dihasilkan | Isi |
|---|---|---|
| `wilayah_operasi.json` | `pusatkan_wilayah.py` | Posko/pangkalan + penegasan `adalah_andaian: true` |
| `sapuan_drone.json` | `rencanakan_sapuan.py` | Rencana sapuan drone, urutan singgah, titik di luar jangkauan, asumsi |
| `patrol_routes.json` | `rutekan_patroli.py` | Rute pengerahan regu darat, geometri jalan nyata dari OSRM |

### Dua rute yang TIDAK boleh dicampur

Kekeliruan yang pernah benar-benar terjadi di produk ini: jalur drone sempat dirutekan lewat jalan raya.

| | Sapuan drone | Pengerahan regu |
|---|---|---|
| Bentuk jalur | **garis lurus** — drone terbang | **mengikuti jalan** — regu bergerak di darat |
| Dibatasi | baterai (~30 menit) | jarak & waktu tempuh |
| Sumber geometri | dihitung sendiri | OSRM di atas OpenStreetMap |

### `sapuan_drone.json` — aturan pelabelan

Perencanaannya **aturan deterministik**, bukan keluaran model — sisi yang sama dengan size-up pada garis pemisah arsitektur.

1. **`di_luar_jangkauan` WAJIB dirender.** Peta yang hanya menggambar jalur terpilih menyiratkan tidak ada yang tertinggal. Separuh kandidat tidak terjangkau satu penerbangan, dan itu justru keputusan yang paling berarti bagi operator.
2. **`asumsi` WAJIB ikut tampil.** Daya tahan 30 menit berasal dari keterangan Dr. Supriyanto; laju 15 m/s dan hover 60 detik/titik adalah **asumsi tim ini yang TIDAK diukur**. Rencana yang tampak presisi tanpa menyebut asumsinya lebih menyesatkan daripada rencana kasar yang jujur.
3. Kandidat adalah **hotspot FIRMS yang belum diverifikasi**, bukan alert. Alert adalah *hasil* verifikasi; merencanakan penerbangan untuk memverifikasinya berarti terbang ke tempat yang sudah diketahui isinya.
4. Posisi posko berlabel **andaian** — Daops yang membawahi koordinat ini tidak diverifikasi.

## Status sumber D1–D6

| # | Sumber | Status | Catatan |
|---|---|---|---|
| D1 | **Open-Meteo** | ✅ dipakai | Presisi titik, ada riwayat 60 hari. Menggerakkan seluruh angka cuaca dan FWI |
| D2 | **BMKG** | ✅ dipakai | Diverifikasi 26 Agu 2026. Hanya menerima `adm4`, jadi dirantai lewat BIG. Mendampingi Open-Meteo, tidak menggantikannya — lihat alasannya di atas |
| D3 | **Indeks bahaya kebakaran** | ✅ dipakai | FWI Sistem Kanada, dihitung sendiri dari van Wagner (1987). Sistem yang sama diadopsi SPBK BMKG |
| D4 | **OpenStreetMap / Overpass** | ✅ dipakai | Diuji di koordinat demo. Memblokir agresif — lihat catatan pembekuan |
| D5 | **Peta gambut** | ⚠️ diganti | Tidak ada layanan gambut/KHG di server publik BIG. Diganti **penutup lahan BIG**, berlabel tegas sebagai pertanyaan yang berbeda |
| D6 | **SIPONGI** | ❌ tidak | Titik integrasi pada slide adopsi, bukan integrasi yang jalan. `sipongi.menlhk.go.id` tidak dapat dijangkau |

## Yang sengaja TIDAK diimplementasikan

| Hal | Alasan |
|---|---|
| **T3 penuturan LLM** | Akan jadi biaya per-inferensi pertama di seluruh sistem, bertabrakan dengan klaim "Rp 0 marginal" di paper dan `estimasi_biaya.md`. Rancangan Bagian 7 juga menggantungnya pada T2 tuntas dan teruji |
| **Menarik angka SPBK dari BMKG** | Portal SPARTAN ber-login tanpa API publik. Men-scrape portal pemerintah yang diproteksi tidak pantas dan tidak andal. Menghitung FWI sendiri justru lebih reproducible untuk paper |
| **Menyimpulkan status KHG dari penutup lahan** | Penetapan KHG adalah dokumen hukum. Peta penutup lahan tidak menjawab pertanyaan itu |

Kalau T3 kelak dikerjakan, bentuk objek di berkas ini adalah masukannya, dan `brief` deterministik tetap menjadi jalur utama saat LLM tidak tersedia (rancangan Bagian 6 butir 4).

## Seluruh sumber tetap tanpa kunci API

Open-Meteo, BMKG, BIG, dan Overpass semuanya gratis tanpa kunci. Klaim **"Rp 0 marginal per inferensi"** di paper dan `estimasi_biaya.md` tetap utuh, dan itu kendala perancangan yang dijaga — bukan kebetulan.
