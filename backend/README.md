---
title: Karhutla Konsol Operator API
emoji: 🔥
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 8000
pinned: false
---

# Backend — Konsol Operator Deteksi Dini Karhutla Gambut

API untuk dashboard operator. Frontend-nya di-deploy terpisah di Vercel.

Frontmatter di atas dibaca **Hugging Face Spaces**. `app_port: 8000` harus cocok
dengan port yang didengarkan `Dockerfile` — jangan diubah salah satunya saja.
Di GitHub, blok itu tampil sebagai tabel; tidak mengganggu.

## Yang dilayani

| Endpoint | Isi |
|---|---|
| `GET /api/health` | Ringkasan jujur asal tiap bagian data |
| `GET /api/alerts` | 10 alert, keluaran batch `fusion_v3_localization.pth` |
| `GET /api/alerts/{id}` | Satu alert |
| `PATCH /api/alerts/{id}/decision` | Catat keputusan operator |
| `GET /api/firms/hotspots` | **Hotspot satelit langsung** dari NASA FIRMS |
| `GET /api/iot/nodes` | Sensor darat simulasi (selalu berlabel simulasi) |
| `GET /api/inference/metrics` | Angka evaluasi untuk Halaman 4 |
| `GET /api/sizeup` | **Konteks size-up** — cuaca (Open-Meteo), indeks FWI, prakiraan resmi BMKG, wilayah & penutup lahan BIG, sumber air & akses OSM, saran peralatan, brief siap tempel |

Bentuk respons alert dikunci `API_CONTRACT.md` — jangan tambah/kurangi field
tanpa menyalin perubahan kontrak ke direktori tim model.

## Kenapa backend ini ada sama sekali

Satu alasan: **`MAP_KEY` FIRMS tidak boleh masuk bundle frontend.** Kalau key
ditaruh di sisi klien, siapa pun bisa membacanya dari devtools. Backend ini
memproksikan panggilan ke NASA supaya key tetap di server.

Sisanya — alert, metrik, citra — sudah berupa keluaran batch yang ikut
ter-bundle di frontend dan **tidak** memerlukan server.

## Runtime

Ringan: `fastapi`, `uvicorn`, `httpx`, `pydantic`, `python-dotenv`. **Tidak ada
torch.** Inference dijalankan offline oleh `scripts/jalankan_inference.py` di
mesin pengembang dan hasilnya di-commit, jadi image tetap ~150 MB.

`scripts/` sengaja dikecualikan dari image lewat `.dockerignore` — isinya butuh
torch dan checkpoint tim model, keduanya tidak ada di runtime.

## Environment variable

| Nama | Wajib | Keterangan |
|---|---|---|
| `MAP_KEY` | ✅ | Key NASA FIRMS. **Simpan sebagai secret**, jangan pernah di berkas. |
| `FRONTEND_ORIGIN` | ✅ | Origin frontend untuk CORS. Boleh beberapa, dipisah koma. Localhost selalu diizinkan otomatis; `*.vercel.app` dicocokkan lewat regex. |
| `MODEL_SERVICE_URL` | — | Kosongkan. Diisi hanya kalau nanti ada layanan inference hidup. |
| `AOI_*` | — | Batas area pencarian FIRMS. Default Sumatra–Kalimantan. |

Lapisan size-up **tidak menambah satu variabel pun**: Open-Meteo, BMKG, BIG, dan
Overpass semuanya gratis tanpa kunci API. Itu kendala perancangan yang dijaga, bukan
kebetulan — begitu lapisan ini butuh kunci berbayar, klaim "Rp 0 marginal per
inferensi" di paper dan `estimasi_biaya.md` ikut gugur. Lihat `SIZEUP_CONTRACT.md`.

## Deploy ke Hugging Face Spaces

1. **huggingface.co** → **New Space** → SDK **Docker** → template **Blank** → visibility **Public**
2. Push **isi folder `backend/`** ke repo Space itu (bukan seluruh repo produk):

   ```bash
   git clone https://huggingface.co/spaces/<user>/<nama-space> hf-space
   cp -r backend/app backend/Dockerfile backend/requirements.txt \
         backend/.dockerignore backend/README.md hf-space/
   cd hf-space && git add -A && git commit -m "backend konsol operator" && git push
   ```

   `README.md` ini harus berada di **root** repo Space — di situlah HF membaca
   frontmatter-nya.

3. Space → **Settings** → **Variables and secrets**:
   - Secret **`MAP_KEY`** = key FIRMS Anda
   - Variable **`FRONTEND_ORIGIN`** = URL Vercel Anda

4. Tunggu build, lalu cek `https://<user>-<nama-space>.hf.space/api/health`

## Deploy ke Render (alternatif)

`render.yaml` di root repo sudah menjadi blueprint siap pakai. Render kini
meminta verifikasi kartu untuk membuat Blueprint, meski layanannya tetap gratis.

## Jalankan lokal

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # isi MAP_KEY
uvicorn app.main:app --reload
```

Docker:

```bash
docker build -t karhutla-api ./backend
docker run -p 8000:8000 -e MAP_KEY=xxx karhutla-api
```

## Skrip pendukung

Semuanya berdiri sendiri, aman dijalankan ulang, dan tidak ada yang butuh kunci API.

| Skrip | Kegunaan |
|---|---|
| `jalankan_inference.py` | Jalankan model batch atas bingkai FLAME 2 → `sample_predictions.json` |
| `bekukan_firms.py` | Bekukan cuplikan hotspot NASA FIRMS untuk deployment statis |
| `bekukan_sizeup.py` | Bekukan konteks size-up per alert (cuaca, FWI, BMKG, BIG, OSM). **Bisa dilanjutkan** — alert yang sudah lengkap dilewati |
| `pusatkan_wilayah.py` | Pusatkan alert & sensor ke satu wilayah operasi yang koheren |
| `rencanakan_sapuan.py` | Rencana sapuan verifikasi drone berbatas baterai atas hotspot FIRMS |
| `rutekan_patroli.py` | Rute pengerahan regu darat mengikuti jalan nyata (OSRM) |
| `sapu_layer_big.py` | Periksa ulang klaim "tidak ada peta gambut di server BIG" |

**Urutan setelah memindahkan wilayah operasi** — koordinat berubah, jadi turunannya ikut basi:

```bash
python backend/scripts/pusatkan_wilayah.py
python backend/scripts/rencanakan_sapuan.py
python backend/scripts/rutekan_patroli.py
uvicorn app.main:app --port 8000     # terminal lain
python backend/scripts/bekukan_sizeup.py
```

**Overpass dan geoportal BIG membatasi laju dengan agresif.** Skrip yang menyentuh keduanya sudah berjeda dan mencoba ulang, tetapi tetap bisa tertahan. Jalankan ulang — yang sudah lengkap dilewati — dan JANGAN merekam demo sebelum keluarannya bersih.
