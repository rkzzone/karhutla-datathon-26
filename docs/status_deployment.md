# Status Deployment & Klaim Fitur

**Untuk:** pengecekan konsistensi klaim paper vs implementasi
**Diverifikasi:** 9 Agustus 2026

Dokumen ini ada supaya tidak ada klaim di paper yang tidak bisa ditunjukkan
saat juri membuka tautannya.

---

## 1. Tautan

| Komponen | URL |
|---|---|
| Konsol operator (frontend) | `https://kh-i5oonu-oa69f4.vercel.app` |
| API (backend) | `https://khsdbuf-dishf23-9fakdjsfjajksdf.vercel.app` |
| Repositori | `github.com/rkzzone/karhutla-konsol-operator` (privat) |

Domain sengaja diacak agar tidak tertebak, dan `X-Robots-Tag: noindex` +
`robots.txt` mencegah pengindeksan. **Ini bukan kontrol akses** — siapa pun
yang memegang tautan bisa membuka.

---

## 2. Matriks fitur

Kolom "bukti" menunjuk cara memverifikasi sendiri.

### ✅ Berfungsi dengan data nyata

| Fitur | Sumber data | Bukti |
|---|---|---|
| Klasifikasi 3 kelas | `fusion_v3_localization.pth` atas 10 bingkai FLAME2 | Panel Alert, badge `sumber model · batch` |
| Keandalan modalitas | Reliability gate Stage 5 | Rentang nyata RGB 15% – 80%, termal 22% – 83% |
| Peta atensi | `segmentation_head`, ambang persentil-90 | Halaman 3, overlay dapat diatur opasitasnya |
| Hotspot satelit | NASA FIRMS VIIRS langsung | Banner "Hotspot satelit langsung", 400 dari ~2.400 |
| Tabel baseline | `ablation1_unimodal_vs_fusion.csv` | Halaman 4: fusi 98,33% · RGB 98,33% · termal 95,00% |
| Kurva degradasi | `degradation_curve.csv` | Halaman 4, 6 titik tau |
| Ablation gating | `ablation2_gating.csv` | Halaman 4 |
| Metrik lokalisasi | `docs/results/ablation3_localization_weak_vs_full.csv` | mIoU 0,5328 · pointing 0,6133 |
| Keputusan operator | State dalam sesi | Tiga tombol, tercatat di jejak keputusan |
| Tema gelap/terang | — | Tombol kanan atas, tersimpan |

### 🟡 Berfungsi, tapi bukan data lapangan

| Fitur | Keadaan sebenarnya | Cara UI menyatakannya |
|---|---|---|
| Sensor darat IoT | **Simulasi**, deterministik terhadap waktu | Label "SIMULASI" di marker, badge, legenda, dan popup |
| Rute patroli | Jalur contoh | Lapisan peta, bukan keluaran model |
| Koordinat alert | **Penempatan simulasi** di gambut Indonesia | Catatan provenans di Halaman 3 |
| Citra RGB/termal | Benchmark publik FLAME 2 (Arizona) | Label "sampel FLAME2" di tiap bingkai + catatan provenans |

### ❌ Belum ada

| Fitur | Status |
|---|---|
| Latensi perangkat edge | Menunggu Stage 8 tim data. Halaman 4 menampilkan "—", bukan angka rekaan |
| Adaptasi domain (LoRA) | Stage 7 tim model **di-skip** — data FLAME3 belum tersedia |
| Layanan inference hidup | Inference dijalankan batch offline, bukan per permintaan |
| Persistensi keputusan | Tersimpan di memori proses; hilang saat restart |
| Uji dengan pengguna nyata | Belum dijalankan — lihat `usability_test/findings.md` |

---

## 3. Klaim yang boleh dan tidak boleh ditulis

### Boleh

> "Model fusi mencapai akurasi 98,33% pada split validasi RFFNet (240 pasangan
> RGB/IR dari FLAME 2)."

> "Saat modalitas didegradasi penuh, fusi turun 1,67 poin akurasi, dibanding
> RGB-saja 5,42 poin dan termal-saja 4,59 poin."

> "Konsol menampilkan hotspot NASA FIRMS VIIRS secara langsung."

> "Keandalan per modalitas ditampilkan di setiap kartu alert, dan menampilkan
> '—' bila belum terukur."

### Tidak boleh

> ~~"Sistem diuji pada lahan gambut Indonesia"~~ — seluruh citra berasal dari
> hutan pinus Arizona. Belum ada satu pun bingkai gambut Indonesia.

> ~~"Sensor IoT memantau kondisi lapangan"~~ — sensornya simulasi.

> ~~"Hasil uji usability menunjukkan…"~~ — belum ada uji dengan pengguna.

> ~~"Akurasi 98,33%"~~ tanpa menyebut splitnya — angka itu berlaku untuk
> RFFNet val Arizona, bukan untuk gambut.

> ~~"Latensi edge X ms"~~ — belum diukur sama sekali.

---

## 4. Perbedaan lokal vs deployment

| Aspek | Lokal | Vercel |
|---|---|---|
| Alert, metrik, citra | Backend / bundle | Bundle (instan) |
| Hotspot FIRMS | Langsung | Langsung, lewat API terpisah |
| Sensor IoT | Waktu server | Waktu server |
| `PATCH` keputusan | Tersimpan di proses | Tersimpan di sesi tab |

Alert sengaja disajikan statis di deployment: ia keluaran batch yang tidak
berubah, sehingga menariknya lewat server hanya menambah perantara dan
menahan tampilan halaman.

**Untuk rekaman video, gunakan lokal** — di sana seluruh lapisan hidup
bersamaan tanpa risiko latensi jaringan.

---

## 5. Cara juri memverifikasi cepat

| Yang dicek | Caranya |
|---|---|
| Data model nyata, bukan mock | Badge kanan atas: `sumber model · batch` |
| Hotspot satelit nyata | Banner peta menyebut jumlah dan "langsung" |
| Angka Halaman 4 nyata | `status data: terukur` + label sumber per stage |
| Kejujuran keadaan kosong | Halaman 4 blok "Latensi edge" menampilkan "—" |
| Provenans citra | Catatan di bawah panel Lokalisasi, Halaman 3 |
| API mentah | `GET /api/firms/hotspots` dan `/api/health` |

---

## 6. Keterbatasan deployment

1. Backend dan frontend adalah dua project Vercel terpisah; keduanya harus
   hidup agar hotspot langsung tampil. Bila backend gagal, konsol otomatis
   turun ke cuplikan bertanggal — bukan layar kosong.
2. Keputusan operator tidak persisten lintas-sesi.
3. Basemap CARTO memerlukan jaringan; tanpa internet peta tampil kosong
   walaupun seluruh data lain tersaji.
4. Diuji pada Chrome/Edge terkini, desktop 1280–1920 px. Tablet didukung;
   ponsel hanya mode lihat-cepat.
