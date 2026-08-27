# API_CONTRACT.md — kontrak kanonik, jangan diduplikasi dengan isi berbeda

**Dokumen ini adalah sumber kebenaran tunggal untuk bentuk data antara model dan konsol.** Setiap perubahan wajib dicatat di `CHANGELOG.md` dan disepakati kedua sisi sebelum diterapkan — sisi model dan sisi konsol tidak boleh berjalan di atas dua versi kontrak yang berbeda.

## Skema respons inference (endpoint utama)

```json
{
  "alert_id": "string, uuid v4",
  "timestamp": "string, ISO 8601, mis. 2026-08-03T08:14:00+07:00",
  "location": {
    "lat": "float",
    "lon": "float"
  },
  "prediction": {
    "label": "fire_smoke | fire_no_smoke | no_fire",
    "confidence": "float, 0.0-1.0"
  },
  "modality_reliability": {
    "rgb": "float, 0.0-1.0, ATAU null jika Stage 5 belum selesai",
    "thermal": "float, 0.0-1.0, ATAU null jika Stage 5 belum selesai"
  },
  "localization": {
    "heatmap_path": "string (path relatif atau URL) ATAU null jika Stage 6 belum selesai",
    "method": "attention_rollout | segmentation_head | null"
  },
  "images": {
    "rgb_url": "string, path atau URL ke citra RGB",
    "thermal_url": "string, path atau URL ke citra termal"
  },
  "source_trigger": "satellite_firms | iot_ground | patrol_scheduled",
  "operator_decision": "ditindaklanjuti | ditunda | alarm_palsu | null"
}
```

## Status field per tanggal (perbarui baris ini saat status berubah — dua-duanya wajib update di hari yang sama)

| Field | Status saat ini | Diisi nyata sejak stage |
|---|---|---|
| `prediction.*` | ✅ nyata (2026-08-05) | Stage 2 |
| `modality_reliability.*` | ✅ nyata (2026-08-05) | Stage 5 |
| `localization.*` | ✅ nyata (2026-08-05) | Stage 6 |

*(tim model: centang kolom ini di file kamu begitu stage selesai dan beri tahu tim produk. Tim produk: centang di file kamu setelah kamu verifikasi sendiri output aslinya cocok skema.)*

## Aturan validasi (kedua pihak wajib patuh)

1. `label` HANYA salah satu dari tiga string persis di atas — bukan variasi kapitalisasi, bukan singkatan.
2. `confidence`, `modality_reliability.rgb`, `modality_reliability.thermal` selalu float dalam rentang [0.0, 1.0] — bukan persen (bukan 92, tapi 0.92).
3. `null` diperbolehkan hanya untuk field yang memang belum tersedia sesuai tabel status di atas — field lain tidak boleh null.
4. `timestamp` selalu ISO 8601 dengan timezone eksplisit.
5. Endpoint TIDAK BOLEH menambah/mengurangi field top-level tanpa mengubah file ini terlebih dulu dan menyalin ke kedua direktori.

## Endpoint yang dipanggil (disepakati, isi detail path/port saat backend jadi)

- `GET /api/alerts` → list of objects sesuai skema di atas, terurut `prediction.confidence` descending
- `GET /api/alerts/{alert_id}` → satu objek sesuai skema di atas
- `PATCH /api/alerts/{alert_id}/decision` → body `{"operator_decision": "..."}`, update field itu

*(tim model dan tim produk: sepakati port/base URL lokal saat kalian pertama integrasi, tulis di sini.)*

## Contoh objek valid (untuk mock data tim produk dan smoke test tim model)

```json
{
  "alert_id": "a1b2c3d4-0000-0000-0000-000000000001",
  "timestamp": "2026-08-03T08:14:00+07:00",
  "location": {"lat": -0.789, "lon": 113.921},
  "prediction": {"label": "fire_smoke", "confidence": 0.92},
  "modality_reliability": {"rgb": 0.35, "thermal": 0.88},
  "localization": {"heatmap_path": "heatmaps/a1b2c3d4.png", "method": "attention_rollout"},
  "images": {"rgb_url": "samples/rgb_001.jpg", "thermal_url": "samples/thermal_001.jpg"},
  "source_trigger": "satellite_firms",
  "operator_decision": null
}
```

## Smoke test wajib sebelum "selesai" diumumkan ke pihak lain

**tim model, sebelum bilang "Stage 2/5/6 selesai" ke tim produk:**
- [x] Jalankan inference service, ambil satu output nyata
- [x] Validasi output itu ter-parse sebagai JSON valid sesuai skema di atas (semua field wajib ada, tipe data benar)
- [x] Contoh output disimpan di `reports/sample_output_stage{N}.json` (`sample_output_stage2.json`, `sample_output_stage5.json`, `sample_output_stage6.json`)

**tim produk, sebelum bilang "sudah pakai data asli" ke grup:**
- [ ] `model_client.py` memanggil endpoint tim model, bukan lagi baca `mock_data/sample_predictions.json`
      — BELUM. Data asli didapat lewat jalur lain: `backend/scripts/jalankan_inference.py`
      memuat `fusion_v3_localization.pth` langsung dan menulis hasilnya ke
      `sample_predictions.json` (batch sekali jalan, bukan layanan hidup). Perlu
      disepakati dengan tim model apakah layanan hidup tetap diperlukan — lihat
      CHANGELOG tim produk 2026-08-08.
- [x] Field yang tadinya null (`modality_reliability`, `localization`) sekarang terisi kalau stage terkait sudah selesai
- [x] Tidak ada error di console saat load Halaman 2 dan 3
