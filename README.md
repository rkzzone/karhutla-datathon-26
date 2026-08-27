# Deteksi Dini Karhutla Gambut

Konsol operator untuk deteksi dini kebakaran hutan dan lahan gambut, dengan fusi
citra RGB–termal dan **gating keandalan per modalitas**.

Sistem menjawab satu pertanyaan operasional: *apakah ada api pada pasangan
bingkai ini, dan seberapa dapat dipercaya tiap kanalnya.* Ketika satu kanal
terdegradasi — RGB tertutup asap, termal terganggu — model tetap memutuskan
dengan benar, dan operator diberi tahu kanal mana yang sedang menopang keputusan
itu.

---

## Kontribusi

Nilai fusi baru terlihat justru ketika kanal memburuk. Pada split validasi
(n = 240), τ adalah tingkat degradasi kanal yang disuntikkan:

| τ | Fusi RGB+termal | RGB saja | Termal saja |
|---:|---:|---:|---:|
| 0,0 | 98,3 % | 98,3 % | 95,0 % |
| 0,4 | 98,3 % | 97,9 % | 97,5 % |
| 0,6 | **98,3 %** | 95,4 % | 93,8 % |
| 0,8 | **97,9 %** | 94,2 % | 92,5 % |
| 1,0 | **96,7 %** | 92,9 % | 90,4 % |

Pada kondisi bersih fusi tidak unggul sama sekali — 98,3 % lawan 98,3 %. Pada
degradasi penuh selisihnya menjadi **+3,8 poin** terhadap RGB saja. Itulah
alasan arsitektur ini menolak menyintesis kanal termal dari RGB, dan alasan
keandalan per modalitas ditampilkan ke operator alih-alih dilebur jadi satu skor.

Sumber angka: `docs/results/hasil_terkoreksi.json`, dihitung ulang setelah audit
label. Kurva lengkap dan uji McNemar ada di direktori yang sama.

---

## Arsitektur

```
PEMICU                DETEKSI                   SIZE-UP                TINDAKAN
FIRMS / sensor    →   fusi RGB+termal       →   konteks & rencana  →   keputusan
laporan warga         keandalan modalitas       cuaca, angin, air      operator
                      lokalisasi                akses, tingkat alat    brief ke
                      ──────────────────        ──────────────────     grup siaga
                      MODEL TERLATIH            ATURAN DETERMINISTIK
                      dievaluasi dengan angka   dapat diaudit
```

Garis pemisah di tengah adalah keputusan rancangan yang disengaja. Di kiri:
dipelajari dari data, dievaluasi dengan metrik di atas. Di kanan: dihitung
dengan aturan terbuka, tidak dilatih, tidak mengklaim akurasi — cuaca, indeks
bahaya kebakaran, sumber air, akses jalan, saran tingkat peralatan.

Rumusannya: **fusi tingkat-fitur untuk RGB dan termal, fusi tingkat-keputusan
untuk cuaca.**

---

## Struktur

```
backend/     API FastAPI — alert, hotspot FIRMS, size-up, simulasi sensor
frontend/    Konsol operator React + Leaflet (4 halaman)
model/       Pelatihan & evaluasi fusi RGB–termal
  configs/     konfigurasi tiap tahap
  runs/        skrip eksekusi berurutan
  analisis/    audit label, kurva degradasi, benchmark CPU
  edge_bench/  ekspor ONNX, kuantisasi INT8, pengukuran
  results/     keluaran run
edge/        Pengukuran perangkat tepi & verifikasi split
docs/        Kontrak API, sistem desain, naskah paper, gambar, hasil evaluasi
render.yaml  Blueprint deploy backend (alternatif Vercel)
```

---

## Menjalankan konsol

Konsol berjalan penuh tanpa backend: seluruh data demo sudah dibekukan ke dalam
bundle.

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

Untuk mode integrasi dengan API:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

lalu isi `VITE_API_BASE` di `frontend/.env.local` — lihat `.env.example`.

### Sumber data luar

Seluruhnya gratis. Hanya NASA FIRMS dan basemap CARTO yang memerlukan kunci,
dan keduanya opsional: tanpa kunci FIRMS konsol memakai cuplikan beku, tanpa
kunci CARTO peta beralih ke Esri Canvas.

| Sumber | Dipakai untuk | Kunci |
|---|---|---|
| NASA FIRMS | Hotspot satelit VIIRS | `MAP_KEY` (server) |
| Open-Meteo | Cuaca titik & riwayat 60 hari | — |
| BMKG | Prakiraan resmi per wilayah | — |
| Badan Informasi Geospasial | Batas wilayah, penutup lahan | — |
| OpenStreetMap / Overpass | Sumber air, akses jalan | — |
| OSRM | Rute pengerahan regu darat | — |
| CARTO Basemaps | Basemap peta | `VITE_CARTO_KEY` (klien) |

---

## Deploy

Repositori ini melayani dua proyek Vercel dari satu sumber:

| Proyek | Root Directory | Environment |
|---|---|---|
| Konsol | `frontend` | `VITE_CARTO_KEY`, `VITE_LIVE_BASE` |
| API | `backend` | `MAP_KEY`, `FRONTEND_ORIGIN` |

`VITE_CARTO_KEY` ditanam ke bundle hasil build dan akan terbaca publik — sifat
semua kunci ubin sisi-klien. Batasi kunci ke domain di dasbor CARTO.

---

## Data & bobot model

Dataset dan bobot model tidak disimpan di repositori ini karena ukurannya.

- Bobot model — https://huggingface.co/Subhaaannn/flame
- Subset dataset & manifes split — https://huggingface.co/datasets/Arga23/karhutla-dataset

Citra latih berasal dari benchmark publik **FLAME 2** (Hopkins et al., 2022),
direkam dengan wahana udara di hutan pinus Arizona. Lisensi dataset terpisah
dari lisensi kode dan **perlu diperiksa sebelum bobot diunggah ulang**.

---

## Keterbatasan

Dinyatakan di muka, karena setiap batas di bawah ini bisa ditanyakan dan
jawabannya lebih baik sudah ada.

**Domain data.** Tidak ada satu pun bingkai gambut Indonesia dalam data latih.
Seluruh angka evaluasi berasal dari FLAME 2 (Arizona). Justifikasi kanal termal
untuk api bawah permukaan gambut bersifat rancangan, bukan bukti empiris.

**Kelas `fire_no_smoke`.** Mati di model — nol prediksi dari 17.856, karena data
latih hanya memuat satu sampel. Kelas ini berdekatan dengan rezim yang justru
disasar rancangan.

**Kalibrasi keyakinan.** Softmax jenuh: sembilan dari sepuluh bingkai
menghasilkan keyakinan 1,0. Sinyal yang benar-benar membedakan alert adalah
keandalan modalitas, yang bervariasi lebar.

**Koordinat.** Model tidak menghasilkan koordinat. Titik pada peta adalah
penempatan simulasi di lahan gambut Indonesia; konsol menyatakannya di setiap
halaman rincian.

**Jangkauan verifikasi udara.** Satu sortie 30 menit menutup radius ~8,6 km,
sekitar 5 % luas satu kabupaten. Sistem ini **tidak mengoperasikan wahana
udara** — ia mengonsumsi citra dari penerbangan yang sudah berlangsung, dan
membantu memilih urutan titik yang diverifikasi lebih dulu.

**Indeks bahaya kebakaran.** Dihitung sendiri dari persamaan terbit Sistem FWI
Kanada (van Wagner, 1987) atas data Open-Meteo. Sistem yang sama diadopsi SPBK
BMKG, tetapi angka di konsol **bukan keluaran BMKG**.

---

## Rujukan

- B. Hopkins et al. (2022). *FLAME 2: Fire detection and modeling — aerial
  multi-spectral image dataset.*
- C. E. van Wagner (1987). *Development and Structure of the Canadian Forest
  Fire Weather Index System.* Forestry Technical Report 35.
- NASA FIRMS — Fire Information for Resource Management System.
