# DESIGN_BRIEF.md — Dashboard Operator Deteksi Dini Karhutla Gambut

**Berlaku untuk:** seluruh desain visual konsol — frontend dan copy backend (pesan galat, label API).
**Status:** token di bagian 2 bersifat final kecuali direvisi tertulis di sini. Jangan improvisasi warna/font baru di tengah coding.

---

## 1. Menjejakkan subjek

Ini bukan situs pemasaran. Ini **instrumen operasional** — dashboard yang dibuka petugas Manggala Agni/BNPB di posko, atau staf HSE di kantor konsesi, untuk memutuskan: kirim tim atau tidak. Audiensnya sedang bekerja, bukan berselancar. Satu tugas halaman: **membantu operator memutuskan cepat dan benar, dengan tahu seberapa yakin sistem terhadap keputusannya sendiri.**

Dunia visual subjek ini: citra termal (palet ironbow — ungu-hitam saat dingin, merah-oranye-kuning saat panas), asap dan kabut gambut, kanopi hutan gelap, peta satelit malam hari, radar/instrumentasi penerbangan. Dari situ kita ambil pilihan desain — bukan dari template dashboard SaaS pada umumnya.

---

## 2. Sistem token

### 2.1 Warna — enam keluarga, digali dari citra termal & lanskap gambut

| Nama | Hex inti | Dari mana | Dipakai untuk |
|---|---|---|---|
| **Ash** (abu bakar) | `#14120F` (950) → `#1C1915` (900) → `#26221C` (800) | Abu sisa bakaran gambut — bukan hitam netral, sedikit hangat | Background, elevasi permukaan (base→card→modal) |
| **Haze** (kabut asap) | `#F2EDE4` (100) → `#B8AFA0` (400) | Cahaya siang tersaring kabut asap tipis | Teks utama, teks sekunder |
| **Canopy** (kanopi) | `#1F3A2E` (600) → `#4A7A5E` (400) | Hijau kanopi hutan gambut | Status aman/terkonfirmasi-bersih — sengaja beda keluarga hue dari skala ember, bukan cuma beda terang-gelap |
| **Ember** (bara — SIGNATURE) | Skala berurutan: `smoke #6B6259` → `ember #C1392B` → `flame #E8752C` → `flare #F5C242` | Palet ironbow kamera termal sungguhan: abu-asap → merah bara → oranye api → kuning terpanas | Skala keparahan/risiko — dipakai identik di badge, legenda peta, DAN sebagai color ramp heatmap itu sendiri |
| **Satellite** (pemicu satelit) | `#5B8AA6` | Biru GIS/citra satelit konvensional | Marker hotspot FIRMS di peta |
| **IoT** (pemicu simulasi) | `#9C7A9E` | Mauve — sengaja beda keluarga dari satellite-blue, menandakan "sumber berbeda" | Marker sensor IoT simulasi |

**Kenapa bukan merah-hijau biasa untuk risiko:** skala Ember berurutan berdasarkan luminansi (gelap→terang), bukan oposisi hue merah-vs-hijau. Ini pilihan aksesibilitas sekaligus pilihan yang jujur terhadap subjek — begitu literal cara kamera termal bekerja. Status "aman" (Canopy hijau) sengaja dijauhkan sepenuhnya dari skala Ember supaya tidak pernah tertukar dengan "risiko rendah" pada skala bara.

**Kritik-diri:** apakah base gelap + satu aksen terang ini jatuh ke default "near-black + neon accent" yang klise? Bedanya di sini: aksennya bukan satu warna neon sembarang, tapi **skala empat-tingkat yang secara harfiah adalah color ramp instrumen sungguhan** (heatmap = UI chrome = elemen yang sama, bukan dekorasi ditempel di atas dashboard gelap generik).

### 2.2 Tipografi — tiga peran

| Peran | Font | Alasan | Dipakai untuk |
|---|---|---|---|
| Display | **Space Grotesk** | Geometris, berkarakter instrumen/HUD | Skor risiko besar, judul halaman |
| Body | **IBM Plex Sans** | Humanis, dukungan diakritik Bahasa Indonesia kuat, dibaca lama tanpa lelah | Deskripsi alert, copy UI |
| Utility/mono | **IBM Plex Mono** | Data instrumen sungguhan butuh tabular figures | Koordinat GPS, timestamp, confidence %, alert ID |

Jangan pakai Inter atau system-ui sebagai display face — terlalu default, kehilangan karakter instrumen yang jadi identitas dashboard ini.

**Skala tipe (rem, basis 16px):**
```
display-xl   3rem / 1.05   tracking -0.03em   → skor risiko hero
display-lg   2rem / 1.1    tracking -0.02em   → judul halaman
heading      1.25rem / 1.3 tracking -0.01em   → judul kartu
body         1rem / 1.7                       → copy default
caption      0.8125rem / 1.5                  → metadata, label
mono-data    0.875rem / 1.4  tabular-nums     → koordinat, timestamp
```

### 2.3 Elemen signature: "Ironbow Risk Ribbon"

Satu elemen yang diingat: garis gradien tipis skala Ember (smoke→ember→flame→flare), dipakai identik di tiga tempat — (a) aksen tepi-kiri tiap `AlertCard`, tebal/posisinya mengikuti confidence, (b) legenda peta, (c) color ramp heatmap `HeatmapOverlay` itu sendiri. Ini satu-satunya tempat kita "berani" secara visual — sisanya tenang dan disiplin.

---

## 3. Layout per halaman (wireframe kasar)

```
HALAMAN 1 — Peta Operasi                    HALAMAN 2 — Panel Alert
┌─────────────────────────────┐             ┌─────────────────────────────┐
│ [toggle layer: FIRMS|IoT|   │             │ Urutkan: risiko▼            │
│  Drone]              [◐]dark│             ├─────────────────────────────┤
├─────────────────────────────┤             │▐█ thumb  label 92%   08:14 │ ← Ironbow ribbon
│                             │             │  badge:termal              │   di tepi kiri
│      PETA (basemap gelap)   │             ├─────────────────────────────┤
│   ● satellite  ● iot        │             │▐▓ thumb  label 61%   08:09 │
│      drone-path             │             ├─────────────────────────────┤
│                             │             │▐░ thumb  no-fire 88% 07:58 │
└─────────────────────────────┘             └─────────────────────────────┘

HALAMAN 3 — Rincian Alert                   HALAMAN 4 — Info Model (untuk juri)
┌───────────┬───────────┬─────┐             ┌─────────────────────────────┐
│  RGB      │  Termal   │ badge│             │ Tabel baseline (mono-data)  │
│  citra    │  citra    │ RGB  │             ├─────────────────────────────┤
├───────────┴───────────┤ Term │             │ Kurva degradasi (chart,     │
│  Heatmap overlay       │      │             │  warna = skala Ember)       │
│  (ramp = Ironbow)      │      │             ├─────────────────────────────┤
├────────────────────────┴─────┤             │ Latensi edge (mono-data)    │
│ [Ditindaklanjuti][Tunda][Palsu]│            └─────────────────────────────┘
└────────────────────────────────┘
```

Halaman 4 boleh terasa lebih "laporan teknis" — grid lebih padat, mono-data dominan — beda sadar dari Halaman 1-3 yang harus tenang dan cepat dibaca saat genting. Tetap pakai token yang sama, bedanya kepadatan dan hierarki, bukan palet baru.

---

## 4. Spesifikasi komponen

| Komponen | Token dipakai | State wajib |
|---|---|---|
| `AlertCard` | Ribbon Ember di tepi kiri, surface `ash-900`, teks `haze-100`/`haze-400` | default, hover (elevasi ke `ash-800`), selected, skeleton-loading |
| `ModalityBadge` | Teks `mono-data`, warna netral `haze-400` kalau `modality_reliability` masih `null` (belum Stage 5) — **jangan tampilkan angka palsu**, tampilkan "—" | terisi, kosong/null, loading |
| `HeatmapOverlay` | Color ramp persis skala Ember 4-tingkat | ada data, `null` (belum Stage 6 → sembunyikan overlay, jangan kotak kosong) |
| `DecisionLog` | Tiga tombol aksi dengan warna netral (bukan Ember — ini aksi operator, bukan skor risiko sistem) | idle, terpilih, terkirim |
| `MapView` | Basemap **gelap** (mis. CARTO Dark Matter via Leaflet, gratis tanpa API key) — basemap terang default akan bentrok total dengan sistem gelap ini | marker satellite (biru), marker iot (mauve, berlabel "simulasi"), drone-path |

---

## 5. Aksesibilitas (wajib, bukan opsional)

- Skala Ember berurutan-luminansi menutup sebagian besar risiko buta warna merah-hijau — tapi tetap **selalu pasangkan warna dengan ikon dan label teks**, jangan pernah encode makna lewat warna saja.
- Status "aman" (Canopy hijau) vs "berisiko" (skala Ember) dibedakan lewat ikon (centang vs api) sekaligus keluarga hue berbeda — bukan cuma terang-gelap.
- Fokus keyboard terlihat jelas (`focus-visible`) di semua elemen interaktif, termasuk marker peta.
- Hormati `prefers-reduced-motion` — animasi peta/badge harus punya fallback statis.
- **Wajib dicek manual sebelum ship:** kontras `haze-400` di atas `ash-900`/`ash-950` — verifikasi dengan contrast checker (target minimum WCAG AA, 4.5:1 untuk teks body). Saya tidak menghitung ini secara presisi di sini — jangan asumsikan lolos tanpa dicek.

---

## 6. Suara & bahasa UI (Bahasa Indonesia)

Prinsip: aktif, spesifik, tanpa basa-basi, konsisten kosakata (kata yang sama selalu berarti hal yang sama di semua tempat). Interface tidak minta maaf dan tidak samar soal apa yang terjadi.

| Situasi | Jangan | Pakai |
|---|---|---|
| Tombol aksi | "Submit" | "Tindak Lanjuti" / "Tandai Alarm Palsu" — dan toast konfirmasi memakai kata yang sama persis: "Ditindaklanjuti" |
| Error API FIRMS gagal | "Terjadi kesalahan" | "Data hotspot satelit tidak bisa dimuat. Coba lagi dalam beberapa menit, atau lanjutkan dengan sumber pemicu lain." |
| Daftar alert kosong | "No data" | "Belum ada alert. Sistem akan menampilkan titik terdeteksi begitu patroli dimulai." |
| Loading | Spinner tanpa teks, atau bahasa dramatis ("Menyalakan mata elang!") | Teks fungsional netral: "Memuat titik patroli…" — topik ini menyangkut bencana nyata, hindari nada heroik/dramatis |
| Badge keandalan | "Confidence: 0.35" (bahasa sistem) | "Bersandar pada termal" — dan istilah ini dipakai identik di badge maupun rincian, jangan ganti-ganti sinonim |

---

## 7. Responsif

Prioritas: **desktop 1280-1920px** (monitor posko) sebagai target utama, **tablet 768-1024px** didukung penuh (supervisor lapangan), **mobile 375-428px** mode "lihat cepat" — daftar alert dan status saja, bukan seluruh fungsi editing. Ini dashboard operasional, bukan situs mobile-first konvensional — urutan prioritas breakpoint dibalik dari kebiasaan umum, dan itu keputusan sadar.

---

## 8. Larangan eksplisit (anti-generik, spesifik ke brief ini)

- Jangan pakai warna default Tailwind (`indigo-500`, `blue-600`, dst.) — semua warna wajib dari tabel Bagian 2.1.
- Jangan pakai merah-hijau biasa untuk status risiko — wajib skala Ember + Canopy sesuai spesifikasi.
- Jangan pakai Inter/system-ui sebagai display face.
- Jangan gunakan `shadow-md` polos — shadow harus bertingkat dan bertoning `ash`.
- Jangan gunakan basemap peta terang/default OSM — wajib basemap gelap.
- Jangan tampilkan angka confidence/reliability palsu saat data belum tersedia (`null`) — tampilkan state kosong yang jujur, bukan angka rekaan.
- Jangan pakai bahasa dramatis/heroik pada teks loading atau error — topik ini nyata dan serius.
